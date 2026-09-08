from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from nlke_hybrid.config import HybridConfig
from nlke_hybrid.providers import GeminiEmbeddingProvider, LocalHTTPEmbeddingProvider


def _config(tmp_path):
    raw = {
        "profiles": {
            "local": {"provider": "local-http", "model": "local", "dimensions": 768, "normalization": "l2/v1", "document_format": "DOC:{title}:{text}", "query_format": "QUERY:{text}", "endpoint": "http://local/embed", "tokenize_endpoint": "http://local/tokenize", "health_endpoint": "http://local/health", "max_input_tokens": 1024},
            "cloud": {"provider": "gemini", "model": "gemini-embedding-001", "dimensions": 768, "normalization": "l2/v1", "document_task_type": "RETRIEVAL_DOCUMENT", "query_task_type": "RETRIEVAL_QUERY", "code_query_task_type": "CODE_RETRIEVAL_QUERY", "max_input_tokens": 1024},
        },
        "enforcement": {"retry_attempts": 0},
    }
    return HybridConfig(tmp_path, tmp_path / "hybrid-rag.json", raw)


def test_local_embedding_formats_and_restores_response_order(tmp_path, monkeypatch):
    config = _config(tmp_path)
    seen = []

    class Response:
        status_code = 200
        is_success = True
        text = ""
        def raise_for_status(self): pass
        def json(self):
            if seen[-1][0].endswith("tokenize"):
                return {"tokens": [1, 2]}
            return {"data": [{"index": 1, "embedding": [2.0] * 768}, {"index": 0, "embedding": [1.0] * 768}]}

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, json):
            seen.append((url, json))
            return Response()

    monkeypatch.setattr("nlke_hybrid.providers.httpx.Client", Client)
    provider = LocalHTTPEmbeddingProvider(config)
    vectors = provider.embed(["first", "second"], purpose="query")
    assert seen[-1][1]["input"] == ["QUERY:first", "QUERY:second"]
    assert vectors[0][0] == 1.0 and vectors[1][0] == 2.0


def test_gemini_uses_declared_retrieval_task_types(tmp_path):
    provider = GeminiEmbeddingProvider(_config(tmp_path))
    seen = {}

    class Models:
        def embed_content(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0] * 768)])

    provider._client = SimpleNamespace(models=Models())
    provider.embed(["query text"], purpose="code_query")
    assert seen["model"] == "gemini-embedding-001"
    assert seen["contents"] == ["query text"]
    assert seen["config"].task_type == "CODE_RETRIEVAL_QUERY"
    assert seen["config"].output_dimensionality == 768
