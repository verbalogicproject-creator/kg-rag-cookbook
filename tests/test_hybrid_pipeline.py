from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import numpy as np

from nlke_hybrid.config import HybridConfig
from nlke_hybrid.declared_core import _tree_sha256

from conftest import canonical_declared_core
from nlke_hybrid.models import EmbeddingProfile, Generator
from nlke_hybrid.pipeline import HybridPipeline
from nlke_hybrid.store import CorpusStore


class FakeProvider:
    def __init__(self, name: str):
        self.profile = EmbeddingProfile(name, "fake", f"{name}-model", 768, "l2/v1", {"purpose": name})
        self.calls = 0

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed(self, texts, *, purpose: str):
        self.calls += 1
        vectors = []
        for text in texts:
            seed = int(hashlib.sha256((purpose + text).encode()).hexdigest()[:8], 16)
            vector = np.zeros(768, dtype=np.float32)
            vector[seed % 768] = 1
            vector[(seed // 768) % 768] = .25
            vectors.append(vector)
        return vectors

    def health(self):
        return {"healthy": True}


class FakeReranker:
    def rerank(self, query, documents):
        return [float(len(documents) - index) for index in range(len(documents))]

    def health(self):
        return {"healthy": True}


class FakeGenerator(Generator):
    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def generate(self, prompt: str):
        return {"answer": "The evidence is supplied here [P001].", "usage": {"total_tokens": 7}, "model": "fake", "finish_reason": "stop", "settings": {}}


def _graph(path: Path, source_path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE nodes (id TEXT PRIMARY KEY,node_type TEXT,name TEXT,qualname TEXT,docstring TEXT,summary TEXT,file_path TEXT,line_start INTEGER,line_end INTEGER,tags TEXT,data TEXT,schema_version INTEGER,created_at TEXT);
    CREATE TABLE edges (id INTEGER PRIMARY KEY,edge_type TEXT,source_id TEXT,target_id TEXT,confidence REAL,extracted_by TEXT,metadata TEXT,created_at TEXT);
    """)
    conn.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("module:alpha", "module", "alpha", "alpha", "", "alpha summary", source_path, 1, 10, "[]", "{}", 1, "fixed"),
        ("module:beta", "module", "beta", "beta", "", "beta summary", "missing.py", 1, 2, "[]", "{}", 1, "fixed"),
    ])
    conn.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?)", [
        (1, "imports", "module:alpha", "module:beta", 1.0, "test", "{}", "fixed"),
        (2, "imports", "module:beta", "module:alpha", 1.0, "test", "{}", "fixed"),
    ])
    conn.commit()
    conn.close()


def _config(tmp_path: Path) -> HybridConfig:
    source = tmp_path / "source"
    source.mkdir()
    (source / "alpha.py").write_text("def alpha():\n    return 'alpha'\n", encoding="utf-8")
    (source / "guide.md").write_text("# Guide\n\nThe alpha symbol describes deterministic retrieval.", encoding="utf-8")
    graph = tmp_path / "estate.db"
    _graph(graph, "alpha.py")
    canonical = canonical_declared_core()
    raw = {
        "schema": "nlke-hybrid-rag/1.0", "storage": {"path": "index.sqlite3"},
        "canonical_dependency": {"name": "declared-core", "path": str(canonical), "revision": "526961e9edbc07f21db39d2183fc0ddc74066dbd", "tree_sha256": _tree_sha256(canonical)},
        "sources": [{"id": "sample", "path": "source", "include": ["**/*.md", "**/*.py"], "exclude": [], "cloud_eligible": True}],
        "graph": {"path": "estate.db", "read_only": True, "max_seed_nodes": 10, "max_expanded_candidates": 50},
        "profiles": {"local": {"provider": "fake", "model": "local-model", "dimensions": 768, "normalization": "l2/v1", "max_input_tokens": 1024}, "cloud": {"provider": "fake", "model": "cloud-model", "dimensions": 768, "normalization": "l2/v1", "max_input_tokens": 1024}},
        "services": {"reranker": {}, "generator": {"max_context_tokens": 4096, "max_output_tokens": 512}},
        "retrieval": {"default_mode": "local", "candidate_limit": 50, "rrf_k": 60, "lexical_weight": 1.0, "graph_weight": .5, "semantic_weight": 1.0, "rerank_candidates": 30, "passage_limit": 8, "per_document_limit": 2, "chunk_tokens": 512, "chunk_overlap_tokens": 64},
        "enforcement": {"retry_attempts": 2},
    }
    return HybridConfig(tmp_path, tmp_path / "hybrid-rag.json", raw)


def _pipeline(tmp_path: Path):
    config = _config(tmp_path)
    local, cloud = FakeProvider("local"), FakeProvider("cloud")
    pipeline = HybridPipeline(config, store=CorpusStore(config.storage_path), providers={"local": local, "cloud": cloud}, reranker=FakeReranker(), generator=FakeGenerator())
    return pipeline, local, cloud


def test_local_mode_makes_no_cloud_requests_and_reuses_local_index(tmp_path):
    pipeline, local, cloud = _pipeline(tmp_path)
    pipeline.index(providers="local")
    indexed_calls = local.calls
    result = pipeline.search("alpha", mode="local")
    assert result["results"]
    assert cloud.calls == 0
    pipeline.index(providers="both")
    assert local.calls == indexed_calls + 1
    assert cloud.calls >= 1
    assert all(profile["complete"] for profile in pipeline.status()["profiles"])
    pipeline.close()


def test_profile_spaces_do_not_mix_and_graph_is_one_hop(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path)
    pipeline.index(providers="both")
    local = pipeline.search("alpha", mode="local", rerank=False)
    cloud = pipeline.search("alpha", mode="cloud", rerank=False)
    assert local["mode"] == "local" and cloud["mode"] == "cloud"
    graph_results = [row for row in local["results"] if row["id"].startswith("graph:")]
    assert all(row["graph_edge"]["hop"] == 1 for row in graph_results)
    assert pipeline.store.status()["graph_edges"] == 2
    pipeline.close()


def test_ask_accepts_resolved_citation(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path)
    pipeline.index(providers="local")
    answer = pipeline.ask("alpha")
    assert answer["status"] == "ok"
    assert answer["citations"] == ["P001"]
    pipeline.close()
