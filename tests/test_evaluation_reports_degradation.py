"""A measurement taken while a component was dead is not a worse measurement.

It is a measurement of a different pipeline.

`HybridPipeline.search` already reports honestly when a stage drops out — it returns
`degradation: [{"component": "reranker", "reason": "... Connection refused"}]` and carries
on with what it still has. That degradation is correct behaviour; retrieval should survive
a dead reranker.

`evaluate()` did not read that field. So a run whose reranker had crashed produced Recall,
MRR and nDCG numbers indistinguishable from a valid run, and two arms of an A/B could
differ only in whether a component happened to be alive. That is exactly what happened:
one arm scored 0.400 with the reranker up, the other 0.350 with it refusing connections,
and the difference was very nearly attributed to a prompt change. The only tell was a
6.7x latency gap that looked wrong.

So degradation now disqualifies as firmly as an outright failure, and names the component.
"""
from __future__ import annotations

from types import SimpleNamespace

from nlke_hybrid.evaluation import evaluate


class _Store:
    def status(self):
        return {"chunks": 3, "documents": 1, "profiles": []}


class FakePipeline:
    """Returns a fixed ranking, optionally reporting a dead component."""

    def __init__(self, *, degraded: str | None):
        self.degraded = degraded
        self.store = _Store()
        self.store.path = SimpleNamespace(exists=lambda: False)

    def search(self, query, *, mode, graph=True, rerank=True):
        out = {"results": [{"id": "chunk:a"}, {"id": "chunk:b"}]}
        if self.degraded:
            out["degradation"] = [{"component": self.degraded, "reason": "Connection refused"}]
        return out


def _queries(tmp_path, count: int):
    import json
    path = tmp_path / "q.json"
    path.write_text(json.dumps({"queries": [
        {"query": f"q{n}", "relevant_ids": ["chunk:a"], "independent": True} for n in range(count)
    ]}), encoding="utf-8")
    return path


def test_a_degraded_run_is_never_qualified(tmp_path):
    report = evaluate(FakePipeline(degraded="reranker"), _queries(tmp_path, 20), modes=("local",))
    assert report["qualification"] == "NOT_ESTABLISHED", (
        "a run with a dead component was reported as a qualified measurement"
    )


def test_the_reason_names_the_component_that_died(tmp_path):
    report = evaluate(FakePipeline(degraded="reranker"), _queries(tmp_path, 20), modes=("local",))
    assert "reranker" in (report["reason"] or ""), "the report does not say WHAT degraded"


def test_degraded_queries_are_counted_per_mode(tmp_path):
    report = evaluate(FakePipeline(degraded="reranker"), _queries(tmp_path, 20), modes=("local",))
    mode = report["modes"]["local"]
    assert mode["degraded_components"] == ["reranker"]
    assert len(mode["degraded"]) == 20, "every affected query must be recorded, not just the first"


def test_an_undegraded_run_with_enough_queries_still_qualifies(tmp_path):
    """Guards the guard: if nothing can qualify, the assertions above prove nothing."""
    report = evaluate(FakePipeline(degraded=None), _queries(tmp_path, 20), modes=("local",))
    assert report["qualification"] == "qualified", report["reason"]
    assert report["modes"]["local"]["degraded"] == []
