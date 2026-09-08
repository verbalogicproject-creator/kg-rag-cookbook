from __future__ import annotations

import numpy as np
import pytest

from nlke_hybrid.models import Chunk, EmbeddingProfile
from nlke_hybrid.store import CorpusStore


def test_store_rejects_malformed_vectors(tmp_path):
    store = CorpusStore(tmp_path / "index.db")
    profile = EmbeddingProfile("local", "test", "model", 768, "l2/v1", {})
    store.replace_sources([{"id": "s", "path": "s", "cloud_eligible": True}], [
        Chunk("chunk:x", "s:doc", "s", "doc", 0, "sha256:x", "body", "title", None, 1, 1, 1, True)
    ])
    with pytest.raises(ValueError, match="wrong dimensions"):
        store.save_embeddings(profile, store.pending_chunks(profile), [np.ones(767, dtype=np.float32)])
    with pytest.raises(ValueError, match="zero norm"):
        store.save_embeddings(profile, store.pending_chunks(profile), [np.zeros(768, dtype=np.float32)])
    store.close()
