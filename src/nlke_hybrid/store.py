from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .models import Chunk, EmbeddingProfile, SearchResult

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, root_path TEXT NOT NULL, cloud_eligible INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  path TEXT NOT NULL, content_hash TEXT NOT NULL, UNIQUE(source_id, path)
);
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE, path TEXT NOT NULL,
  ordinal INTEGER NOT NULL, content_hash TEXT NOT NULL, text TEXT NOT NULL, title TEXT NOT NULL,
  symbol TEXT, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, token_count INTEGER NOT NULL,
  cloud_eligible INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_chunks_symbol ON chunks(symbol);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, title, symbol, text);
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, identity_json TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
  content_hash TEXT NOT NULL, dimensions INTEGER NOT NULL, vector BLOB NOT NULL,
  PRIMARY KEY(chunk_id, profile_id)
);
CREATE TABLE IF NOT EXISTS index_jobs (
  id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), status TEXT NOT NULL,
  outstanding INTEGER NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS graph_nodes (
  id TEXT PRIMARY KEY, node_type TEXT NOT NULL, name TEXT NOT NULL, qualname TEXT NOT NULL,
  summary TEXT NOT NULL, file_path TEXT, line_start INTEGER, line_end INTEGER, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_edges (
  id INTEGER PRIMARY KEY, edge_type TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
  confidence REAL NOT NULL, metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_graph_edge_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edge_target ON graph_edges(target_id);
"""


def profile_id(profile: EmbeddingProfile) -> str:
    body = json.dumps(profile.identity(), sort_keys=True, separators=(",", ":"))
    return "profile:" + hashlib.sha256(body.encode()).hexdigest()


class CorpusStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def register_profile(self, profile: EmbeddingProfile) -> str:
        ident = profile_id(profile)
        canonical = json.dumps(profile.identity(), sort_keys=True, separators=(",", ":"))
        with self.conn:
            existing = self.conn.execute("SELECT identity_json FROM profiles WHERE id = ?", (ident,)).fetchone()
            if existing and existing["identity_json"] != canonical:
                raise ValueError("embedding profile identity collision")
            self.conn.execute(
                "INSERT OR IGNORE INTO profiles(id, name, identity_json) VALUES (?, ?, ?)",
                (ident, profile.name, canonical),
            )
        return ident

    def replace_sources(self, sources: Sequence[dict[str, Any]], chunks: Sequence[Chunk]) -> dict[str, int]:
        """Commit each declared source delta and its FTS projection atomically."""
        by_document: dict[str, list[Chunk]] = defaultdict(list)
        for chunk in chunks:
            by_document[chunk.document_id].append(chunk)
        by_source: dict[str, dict[str, list[Chunk]]] = defaultdict(dict)
        for document_id, items in by_document.items():
            by_source[items[0].source_id][document_id] = items
        inserted = 0
        with self.conn:
            for source in sources:
                source_id = source["id"]
                self.conn.execute(
                    "INSERT INTO sources(id, root_path, cloud_eligible) VALUES (?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET root_path=excluded.root_path, cloud_eligible=excluded.cloud_eligible",
                    (source_id, str(source["path"]), int(bool(source["cloud_eligible"]))),
                )
                incoming = by_source.get(source_id, {})
                old = {
                    row["id"]: row["content_hash"]
                    for row in self.conn.execute("SELECT id, content_hash FROM documents WHERE source_id = ?", (source_id,))
                }
                for document_id in sorted(set(old) - set(incoming)):
                    self.conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                for document_id, entries in sorted(incoming.items()):
                    document_hash = "sha256:" + hashlib.sha256(
                        "".join(item.content_hash for item in entries).encode()
                    ).hexdigest()
                    if old.get(document_id) == document_hash:
                        continue
                    self.conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                    self.conn.execute(
                        "INSERT INTO documents(id, source_id, path, content_hash) VALUES (?, ?, ?, ?)",
                        (document_id, source_id, entries[0].path, document_hash),
                    )
                    for item in entries:
                        self.conn.execute(
                            "INSERT INTO chunks(id, document_id, source_id, path, ordinal, content_hash, text, title, symbol, line_start, line_end, token_count, cloud_eligible) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (item.id, item.document_id, item.source_id, item.path, item.ordinal, item.content_hash,
                             item.text, item.title, item.symbol, item.line_start, item.line_end, item.token_count,
                             int(item.cloud_eligible)),
                        )
                        inserted += 1
            self.conn.execute("DELETE FROM chunks_fts")
            self.conn.execute(
                "INSERT INTO chunks_fts(rowid, chunk_id, title, symbol, text) "
                "SELECT rowid, id, title, COALESCE(symbol, ''), text FROM chunks ORDER BY id"
            )
        return {"documents": len(by_document), "chunks_inserted": inserted, "chunks_total": self.chunk_count()}

    def sync_graph(self, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM graph_edges")
            self.conn.execute("DELETE FROM graph_nodes")
            self.conn.executemany(
                "INSERT INTO graph_nodes(id,node_type,name,qualname,summary,file_path,line_start,line_end,data) VALUES (?,?,?,?,?,?,?,?,?)",
                [(node["id"], node["node_type"], node["name"], node["qualname"], node["summary"],
                  node["file_path"], node["line_start"], node["line_end"], node["data"]) for node in nodes],
            )
            self.conn.executemany(
                "INSERT INTO graph_edges(id,edge_type,source_id,target_id,confidence,metadata) VALUES (?,?,?,?,?,?)",
                [(edge["id"], edge["edge_type"], edge["source_id"], edge["target_id"], edge["confidence"], edge["metadata"])
                 for edge in edges],
            )

    def pending_chunks(self, profile: EmbeddingProfile) -> list[Chunk]:
        ident = self.register_profile(profile)
        eligibility = "AND c.cloud_eligible = 1" if profile.name == "cloud" else ""
        rows = self.conn.execute(
            "SELECT c.* FROM chunks c LEFT JOIN embeddings e ON e.chunk_id=c.id AND e.profile_id=? "
            "WHERE e.chunk_id IS NULL " + eligibility + " ORDER BY c.id", (ident,)
        ).fetchall()
        return [self._chunk(row) for row in rows]

    def save_embeddings(self, profile: EmbeddingProfile, chunks: Sequence[Chunk], vectors: Sequence[np.ndarray]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("embedding response order/count does not match request")
        ident = self.register_profile(profile)
        rows: list[tuple[Any, ...]] = []
        for chunk, vector in zip(chunks, vectors):
            normalized = np.asarray(vector, dtype=np.float32)
            if normalized.ndim != 1 or normalized.shape[0] != profile.dimensions:
                raise ValueError(f"{profile.name} vector for {chunk.id} has wrong dimensions")
            if not np.isfinite(normalized).all():
                raise ValueError(f"{profile.name} vector for {chunk.id} is non-finite")
            norm = float(np.linalg.norm(normalized))
            if norm == 0.0:
                raise ValueError(f"{profile.name} vector for {chunk.id} has zero norm")
            normalized = normalized / norm
            rows.append((chunk.id, ident, chunk.content_hash, profile.dimensions, normalized.tobytes()))
        with self.conn:
            self.conn.executemany(
                "INSERT INTO embeddings(chunk_id,profile_id,content_hash,dimensions,vector) VALUES (?,?,?,?,?) "
                "ON CONFLICT(chunk_id,profile_id) DO UPDATE SET content_hash=excluded.content_hash, dimensions=excluded.dimensions, vector=excluded.vector",
                rows,
            )

    def start_job(self, profile: EmbeddingProfile, outstanding: int) -> str:
        ident = self.register_profile(profile)
        job_id = "job:" + hashlib.sha256(f"{ident}:{outstanding}".encode()).hexdigest()
        with self.conn:
            self.conn.execute(
                "INSERT INTO index_jobs(id,profile_id,status,outstanding,error) VALUES (?,?,?,?,NULL) "
                "ON CONFLICT(id) DO UPDATE SET status='running', outstanding=excluded.outstanding, error=NULL",
                (job_id, ident, "running", outstanding),
            )
        return job_id

    def finish_job(self, job_id: str, *, error: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE index_jobs SET status=?, outstanding=?, error=? WHERE id=?",
                ("complete" if error is None else "incomplete", 0 if error is None else self._job_outstanding(job_id), error, job_id),
            )

    def _job_outstanding(self, job_id: str) -> int:
        row = self.conn.execute("SELECT outstanding FROM index_jobs WHERE id=?", (job_id,)).fetchone()
        return int(row["outstanding"]) if row else 0

    def lexical_rows(self, adapter: Any, query: str, limit: int) -> list[dict[str, Any]]:
        return adapter.lexical(self.conn, query, limit)

    def exact_rows(self, query: str, limit: int) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        rows = self.conn.execute(
            "SELECT *, 'chunks' AS 'table' FROM chunks WHERE id=? OR symbol=? OR path=? OR path LIKE ? ORDER BY id LIMIT ?",
            (query, query, query, "%/" + query, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def dense_rows(self, profile: EmbeddingProfile, query_vector: np.ndarray, limit: int) -> list[dict[str, Any]]:
        ident = self.register_profile(profile)
        rows = self.conn.execute(
            "SELECT c.*, e.dimensions, e.vector FROM embeddings e JOIN chunks c ON c.id=e.chunk_id WHERE e.profile_id=? ORDER BY c.id",
            (ident,),
        ).fetchall()
        if not rows:
            return []
        query_vector = np.asarray(query_vector, dtype=np.float32)
        if query_vector.shape != (profile.dimensions,) or not np.isfinite(query_vector).all():
            raise ValueError("invalid query vector for selected profile")
        norm = float(np.linalg.norm(query_vector))
        if norm == 0:
            raise ValueError("zero-norm query vector")
        query_vector = query_vector / norm
        scored: list[dict[str, Any]] = []
        for row in rows:
            if int(row["dimensions"]) != profile.dimensions:
                raise ValueError("corrupt index: stored vector dimensions do not match profile")
            vector = np.frombuffer(row["vector"], dtype=np.float32)
            if vector.shape != (profile.dimensions,) or not np.isfinite(vector).all():
                raise ValueError("corrupt index: invalid stored vector")
            item = dict(row)
            item["table"] = "chunks"
            item["dense_score"] = float(np.dot(query_vector, vector))
            scored.append(item)
        return sorted(scored, key=lambda item: (-item["dense_score"], item["id"]))[:limit]

    def rows_for_ids(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        unique = sorted(set(ids))
        if not unique:
            return {}
        placeholders = ",".join("?" for _ in unique)
        rows = self.conn.execute(f"SELECT *, 'chunks' AS 'table' FROM chunks WHERE id IN ({placeholders})", unique).fetchall()
        return {row["id"]: dict(row) for row in rows}

    def status(self) -> dict[str, Any]:
        coverage = []
        for row in self.conn.execute("SELECT id, name, identity_json FROM profiles ORDER BY id"):
            eligible = "c.cloud_eligible = 1" if row["name"] == "cloud" else "1=1"
            total = self.conn.execute(f"SELECT count(*) FROM chunks c WHERE {eligible}").fetchone()[0]
            embedded = self.conn.execute(
                f"SELECT count(*) FROM embeddings e JOIN chunks c ON c.id=e.chunk_id WHERE e.profile_id=? AND {eligible}",
                (row["id"],),
            ).fetchone()[0]
            coverage.append({"profile": row["name"], "profile_id": row["id"], "embedded": embedded, "eligible": total,
                             "complete": embedded == total, "identity": json.loads(row["identity_json"])})
        jobs = [dict(row) for row in self.conn.execute("SELECT * FROM index_jobs ORDER BY id")]
        return {"storage": str(self.path), "chunks": self.chunk_count(), "documents": self.document_count(), "profiles": coverage, "jobs": jobs,
                "graph_nodes": self.conn.execute("SELECT count(*) FROM graph_nodes").fetchone()[0], "graph_edges": self.conn.execute("SELECT count(*) FROM graph_edges").fetchone()[0]}

    def chunk_count(self) -> int:
        return int(self.conn.execute("SELECT count(*) FROM chunks").fetchone()[0])

    def document_count(self) -> int:
        return int(self.conn.execute("SELECT count(*) FROM documents").fetchone()[0])

    @staticmethod
    def _chunk(row: sqlite3.Row) -> Chunk:
        return Chunk(
            id=row["id"], document_id=row["document_id"], source_id=row["source_id"], path=row["path"], ordinal=row["ordinal"],
            content_hash=row["content_hash"], text=row["text"], title=row["title"], symbol=row["symbol"],
            line_start=row["line_start"], line_end=row["line_end"], token_count=row["token_count"], cloud_eligible=bool(row["cloud_eligible"]),
        )


def row_to_result(row: dict[str, Any]) -> SearchResult:
    return SearchResult(
        id=row["id"], source_id=row["source_id"], parent_id=row["document_id"], path=row["path"],
        line_start=row["line_start"], line_end=row["line_end"], text=row["text"], title=row["title"],
        symbol=row.get("symbol"), score=float(row.get("rrf_score", row.get("dense_score", 0.0))),
        signals={key: row[key] for key in ("bm25_rank", "dense_score", "rrf_score", "rrf_sources") if key in row},
    )
