from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Sequence

from .errors import ConfigError


def _rank_metrics(retrieved: list[str], relevant: set[str], limit: int) -> tuple[float, float, float]:
    top = retrieved[:limit]
    recall = len(set(top) & relevant) / len(relevant) if relevant else 1.0
    reciprocal = next((1.0 / rank for rank, identifier in enumerate(top, 1) if identifier in relevant), 0.0)
    dcg = sum(1.0 / __import__("math").log2(rank + 1) for rank, identifier in enumerate(top, 1) if identifier in relevant)
    ideal = sum(1.0 / __import__("math").log2(rank + 1) for rank in range(1, min(len(relevant), limit) + 1))
    return recall, reciprocal, dcg / ideal if ideal else 1.0


def evaluate(pipeline: Any, query_file: str | Path, *, modes: Sequence[str] = ("lexical", "local", "cloud", "both"), graph: bool = True, rerank: bool = True) -> dict[str, Any]:
    path = Path(query_file)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load evaluation file {path}: {exc}") from exc
    queries = payload.get("queries") if isinstance(payload, dict) else payload
    if not isinstance(queries, list) or not queries:
        raise ConfigError("evaluation JSON must contain a non-empty queries list")
    independent = [item for item in queries if isinstance(item, dict) and item.get("independent") is True]
    reports: dict[str, Any] = {}
    for mode in modes:
        recalls5: list[float] = []
        recalls10: list[float] = []
        mrr10: list[float] = []
        ndcg10: list[float] = []
        latencies: list[float] = []
        failures: list[dict[str, str]] = []
        degraded: list[dict[str, str]] = []
        for item in queries:
            if not isinstance(item, dict) or not isinstance(item.get("query"), str) or not isinstance(item.get("relevant_ids"), list):
                raise ConfigError("each evaluation query needs query and relevant_ids")
            started = time.perf_counter()
            try:
                result = pipeline.search(item["query"], mode=mode, graph=graph, rerank=rerank)
            except Exception as exc:
                failures.append({"query": item["query"], "error": str(exc)})
                continue
            latencies.append((time.perf_counter() - started) * 1000)
            # A run whose reranker died still produces numbers, and they look exactly like
            # a valid measurement. The pipeline reports the dropout honestly in
            # `degradation`; this harness used to ignore it, so two arms of an A/B could
            # differ only in whether a component happened to be alive -- which is how a
            # 6.7x latency gap and a whole scoring difference got attributed to a prompt.
            for entry in result.get("degradation") or []:
                degraded.append({"query": item["query"], **entry})
            actual = [row["id"] for row in result["results"]]
            expected = set(item["relevant_ids"])
            r5, _, _ = _rank_metrics(actual, expected, 5)
            r10, mrr, ndcg = _rank_metrics(actual, expected, 10)
            recalls5.append(r5); recalls10.append(r10); mrr10.append(mrr); ndcg10.append(ndcg)
        percentile = lambda values, fraction: sorted(values)[max(0, min(len(values) - 1, round((len(values) - 1) * fraction)))] if values else None
        reports[mode] = {
            "queries_run": len(recalls10), "failures": failures,
            # Named components that dropped out mid-run, and how many queries each affected.
            "degraded": degraded,
            "degraded_components": sorted({entry.get("component", "?") for entry in degraded}),
            "Recall@5": statistics.mean(recalls5) if recalls5 else None,
            "Recall@10": statistics.mean(recalls10) if recalls10 else None,
            "MRR@10": statistics.mean(mrr10) if mrr10 else None,
            "nDCG@10": statistics.mean(ndcg10) if ndcg10 else None,
            "latency_ms": {"p50": percentile(latencies, .5), "p95": percentile(latencies, .95)},
        }
    state = pipeline.store.status()
    # Degradation disqualifies as firmly as an outright failure: a measurement taken while
    # the reranker was refusing connections is not a worse measurement, it is a measurement
    # of a different pipeline.
    any_degraded = any(report["degraded"] for report in reports.values())
    qualification = (
        "qualified"
        if len(independent) >= 20
        and all(not report["failures"] for report in reports.values())
        and not any_degraded
        else "NOT_ESTABLISHED"
    )
    return {
        "operation": "evaluate", "qualification": qualification,
        "reason": None if qualification == "qualified" else (
            "a component degraded mid-run: "
            + ", ".join(sorted({e.get("component", "?") for r in reports.values() for e in r["degraded"]}))
            if any_degraded
            else "requires at least 20 independently authored blind queries and no hard-contract failures"
        ),
        "corpus": {"chunks": state["chunks"], "documents": state["documents"]}, "sample_size": len(queries),
        "independent_blind_queries": len(independent), "judge": payload.get("judge") if isinstance(payload, dict) else None,
        "modes": reports, "index_coverage": state["profiles"], "storage_bytes": pipeline.store.path.stat().st_size if pipeline.store.path.exists() else 0,
        "citation_validity": "NOT_OBSERVED: retrieval evaluation does not generate answers", "cloud_token_usage": "NOT_OBSERVED: provider receipt did not report tokens",
        "ablations": {"graph": graph, "reranker": rerank},
    }
