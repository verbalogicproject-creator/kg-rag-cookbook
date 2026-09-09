"""Chunk identity must be a property of the corpus, not of the command line.

`_fit_to_provider_budgets` re-splits chunks until a provider accepts them, and then
assigns `chunk.id` from `document_id:ordinal:content_hash`. Those two jobs in one method
mean that whichever budget the fit runs against decides what the chunks are *called*.

Fitting against only the selected provider therefore made chunk ids depend on
`--providers`. The consequence was not subtle: indexing the same corpus with a
1024-dimension model re-fitted it to that model's tokenizer, minted new ids for every
chunk that moved, and the `documents -> chunks -> embeddings` cascade deleted the
previously indexed model's vectors for them. Evaluation ground truth stopped resolving,
and the older model could no longer embed the corpus at all — chunks fitted to the newer
tokenizer exceeded its context and the server rejected the batch outright.

Two embedders cannot be compared unless they are scored over the same chunks, so the fit
now runs against every configured budget. These assertions pin both halves of that: the
ids do not move when the selection changes, and every chunk fits the tightest configured
budget rather than merely the selected one.
"""
from __future__ import annotations

from pathlib import Path

from nlke_hybrid.config import HybridConfig
from nlke_hybrid.declared_core import _tree_sha256

from conftest import canonical_declared_core
from nlke_hybrid.ingest import scan_chunks
from nlke_hybrid.models import EmbeddingProfile
from nlke_hybrid.pipeline import HybridPipeline
from nlke_hybrid.store import CorpusStore

TIGHT = 12    # cloud: forces repeated splitting
ROOMY = 4096  # local: would accept the text whole


class BudgetProvider:
    """Only the budget matters here; embedding is never called."""

    def __init__(self, name: str, dimensions: int = 768):
        self.profile = EmbeddingProfile(name, "fake", f"{name}-model", dimensions, "l2/v1", {})

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed(self, texts, *, purpose: str):  # pragma: no cover - not exercised
        raise AssertionError("fitting must not embed")

    def health(self):
        return {"healthy": True}


def _config(tmp_path: Path) -> HybridConfig:
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "long.md").write_text(
        "# Heading\n\n" + " ".join(f"word{n}" for n in range(400)), encoding="utf-8"
    )
    canonical = canonical_declared_core()
    raw = {
        "schema": "nlke-hybrid-rag/1.0", "storage": {"path": "index.sqlite3"},
        "canonical_dependency": {"name": "declared-core", "path": str(canonical),
                                 "revision": "526961e9edbc07f21db39d2183fc0ddc74066dbd",
                                 "tree_sha256": _tree_sha256(canonical)},
        "sources": [{"id": "s", "path": "source", "include": ["**/*.md"], "exclude": [], "cloud_eligible": True}],
        "graph": {"path": "estate.db", "read_only": True, "max_seed_nodes": 10, "max_expanded_candidates": 50},
        "profiles": {
            "local": {"provider": "fake", "model": "l", "dimensions": 768, "normalization": "l2/v1", "max_input_tokens": ROOMY},
            "cloud": {"provider": "fake", "model": "c", "dimensions": 768, "normalization": "l2/v1", "max_input_tokens": TIGHT},
        },
        "services": {"reranker": {}, "generator": {"max_context_tokens": 4096, "max_output_tokens": 512}},
        "retrieval": {"default_mode": "local", "candidate_limit": 50, "rrf_k": 60, "lexical_weight": 1.0,
                      "graph_weight": .5, "semantic_weight": 1.0, "rerank_candidates": 30, "passage_limit": 8,
                      "per_document_limit": 2, "chunk_tokens": 512, "chunk_overlap_tokens": 64},
        "enforcement": {"retry_attempts": 2},
    }
    return HybridConfig(tmp_path, tmp_path / "hybrid-rag.json", raw)


def _fit(tmp_path: Path, selected):
    config = _config(tmp_path)
    pipeline = HybridPipeline(
        config, store=CorpusStore(config.storage_path),
        providers={"local": BudgetProvider("local"), "cloud": BudgetProvider("cloud")},
        reranker=object(), generator=object(),
    )
    chunks = [chunk for _, _, chunk in [(None, None, c) for c in scan_chunks(config)]]
    return pipeline._fit_to_provider_budgets(chunks, selected)


def test_chunk_ids_do_not_depend_on_which_provider_was_selected(tmp_path):
    local_only = [c.id for c in _fit(tmp_path / "a", ["local"])]
    cloud_only = [c.id for c in _fit(tmp_path / "b", ["cloud"])]
    both = [c.id for c in _fit(tmp_path / "c", ["local", "cloud"])]
    assert local_only == cloud_only == both, (
        "chunk identity changed with the provider selection; two embedders can no longer "
        "be compared on the same chunks, and re-indexing one cascades away the other's vectors"
    )


def test_every_chunk_fits_the_tightest_configured_budget(tmp_path):
    """Not merely the selected one — otherwise the unselected model cannot embed the corpus."""
    counter = BudgetProvider("cloud")
    for chunk in _fit(tmp_path, ["local"]):
        assert counter.count_tokens(chunk.text) <= TIGHT, (
            f"chunk {chunk.id} fits the selected provider but exceeds the tightest configured "
            f"budget ({TIGHT}); the other model would reject it"
        )


def test_a_tight_budget_actually_forces_splitting(tmp_path):
    """Guards the guard: if nothing split, the assertions above prove nothing."""
    assert len(_fit(tmp_path, ["local"])) > 1
