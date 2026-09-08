from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Sequence


class EstateGraphAdapter:
    """Read the estate graph only through SQLite's immutable read-only URI."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        uri = f"file:{self.path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            nodes = [dict(row) for row in conn.execute(
                "SELECT id,node_type,name,qualname,summary,file_path,line_start,line_end,data FROM nodes ORDER BY id"
            )]
            edges = [dict(row) for row in conn.execute(
                "SELECT id,edge_type,source_id,target_id,confidence,metadata FROM edges ORDER BY id"
            )]
        finally:
            conn.close()
        node_ids = {node["id"] for node in nodes}
        dangling = [str(edge["id"]) for edge in edges if edge["source_id"] not in node_ids or edge["target_id"] not in node_ids]
        return nodes, edges, dangling


def expand_one_hop(store: Any, seeds: Sequence[dict[str, Any]], *, max_seeds: int, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    """Expand declared graph edges one hop with stable, bounded ordering."""
    conn = store.conn
    seed_nodes: list[tuple[int, str]] = []
    for rank, seed in enumerate(seeds[:max_seeds], 1):
        rows = conn.execute(
            "SELECT id FROM graph_nodes WHERE qualname=? OR name=? OR file_path=? OR file_path LIKE ? ORDER BY id",
            (seed.get("symbol") or "", seed.get("title") or "", seed.get("path") or "", "%/" + (seed.get("path") or "")),
        ).fetchall()
        seed_nodes.extend((rank, row["id"]) for row in rows)
    out: list[dict[str, Any]] = []
    dangling: list[str] = []
    seen: set[str] = set()
    for seed_rank, node_id in sorted(set(seed_nodes), key=lambda pair: (pair[0], pair[1])):
        edges = conn.execute(
            "SELECT * FROM graph_edges WHERE source_id=? OR target_id=? ORDER BY id", (node_id, node_id)
        ).fetchall()
        for edge in edges:
            neighbor = edge["target_id"] if edge["source_id"] == node_id else edge["source_id"]
            node = conn.execute("SELECT * FROM graph_nodes WHERE id=?", (neighbor,)).fetchone()
            if node is None:
                dangling.append(str(edge["id"]))
                continue
            chunk = None
            if node["file_path"]:
                chunk = conn.execute(
                    "SELECT *, 'chunks' AS 'table' FROM chunks WHERE path=? OR path LIKE ? ORDER BY id LIMIT 1",
                    (node["file_path"], "%/" + node["file_path"]),
                ).fetchone()
            edge_data = {
                "id": edge["id"], "type": edge["edge_type"], "source_id": edge["source_id"], "target_id": edge["target_id"],
                "confidence": edge["confidence"], "metadata": json.loads(edge["metadata"]), "hop": 1, "seed_rank": seed_rank,
            }
            if chunk:
                item = dict(chunk)
                item["graph_edge"] = edge_data
            else:
                item = {
                    "id": "graph:" + node["id"], "table": "graph_nodes", "source_id": "estate-graph",
                    "document_id": "graph:" + node["id"], "path": "graph://" + node["id"], "line_start": node["line_start"],
                    "line_end": node["line_end"], "title": node["name"] or node["id"], "symbol": node["qualname"] or None,
                    "text": node["summary"] or node["name"] or node["id"], "graph_edge": edge_data,
                }
            if item["id"] not in seen:
                seen.add(item["id"])
                out.append(item)
            if len(out) >= limit:
                return out, dangling
    return out, dangling
