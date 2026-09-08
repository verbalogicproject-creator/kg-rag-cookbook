from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import HybridConfig, load_config, validate_config
from .declared_core import DeclaredCoreAdapter
from .errors import ConfigError, ContextOverflow, ProviderError
from .graph import EstateGraphAdapter, expand_one_hop
from .ingest import scan_chunks
from .models import Chunk, Generator, SearchResult
from .providers import BGEReranker, GeminiEmbeddingProvider, LocalHTTPEmbeddingProvider, QwenGenerator
from .store import CorpusStore, row_to_result

_CITATION_RE = re.compile(r"\[(P\d+(?:\s*,\s*P\d+)*)\]")
_SYSTEM_PROMPT = "Answer only from supplied passages. Cite every factual claim with one or more passage IDs in square brackets."


class HybridPipeline:
    def __init__(self, config: HybridConfig | str | Path = "hybrid-rag.json", *, store: CorpusStore | None = None,
                 providers: dict[str, Any] | None = None, reranker: Any | None = None, generator: Generator | None = None):
        self.config = load_config(config) if not isinstance(config, HybridConfig) else config
        self.store = store or CorpusStore(self.config.storage_path)
        self.core = DeclaredCoreAdapter(self.config)
        self.providers = providers or {
            "local": LocalHTTPEmbeddingProvider(self.config),
            "cloud": GeminiEmbeddingProvider(self.config),
        }
        self.reranker = reranker if reranker is not None else BGEReranker(self.config)
        self.generator = generator if generator is not None else QwenGenerator(self.config)

    def close(self) -> None:
        self.store.close()

    def _selected_providers(self, providers: str | Sequence[str]) -> list[str]:
        if isinstance(providers, str):
            names = ["local", "cloud"] if providers == "both" else [providers]
        else:
            names = list(providers)
        if not names or any(name not in {"local", "cloud"} for name in names):
            raise ConfigError("providers must be local, cloud, or both")
        return names

    def _formatted_document(self, provider: Any, chunk: Chunk) -> str:
        if hasattr(provider, "format"):
            return provider.format(chunk.text, purpose="document", title=chunk.title)
        return chunk.text

    def _fit_to_provider_budgets(self, chunks: Sequence[Chunk], selected: Sequence[str]) -> list[Chunk]:
        """Split a chunk again until EVERY configured provider accepts its full input.

        Every configured one, not merely the selected one -- because this method also
        assigns `chunk.id` (below), so fitting against a subset makes chunk identity a
        function of which provider you happened to index with.

        That was not theoretical. Indexing with a 1024-dimension model re-fitted the corpus
        to its tokenizer, minted different ids for the chunks that moved, and the cascade
        from `documents` -> `chunks` -> `embeddings` deleted the OTHER profile's vectors for
        them. Two evaluation ground-truth ids stopped resolving, and the previously indexed
        model could no longer embed its own corpus at all: chunks fitted to the newer
        tokenizer exceeded the older model's context and the server rejected the batch.

        Fitting against all configured budgets makes chunk identity a property of the
        corpus instead of the command line, so two embedders can be compared on the same
        chunks -- which is the only way that comparison means anything -- and every
        configured model can accept every chunk. `selected` is retained for the
        cloud-eligibility skip, which is a per-provider content rule, not a budget.
        """
        pending = list(chunks)
        for name in sorted(self.providers):
            provider = self.providers[name]
            limit = int(provider.profile.dimensions and self.config.raw["profiles"][name]["max_input_tokens"])
            fitted: list[Chunk] = []
            for chunk in pending:
                # `cloud_eligible` is a stable property of the CHUNK, so skipping on it
                # keeps the fit selection-independent. Skipping on `name not in selected`
                # would not -- it would put the tight budget back behind the command line,
                # which is the whole defect this method was changed to remove.
                if name == "cloud" and not chunk.cloud_eligible:
                    fitted.append(chunk)
                    continue
                queue = [chunk]
                while queue:
                    current = queue.pop(0)
                    formatted = self._formatted_document(provider, current)
                    if provider.count_tokens(formatted) <= limit:
                        fitted.append(current)
                        continue
                    words = current.text.split()
                    if len(words) < 2:
                        raise ContextOverflow(f"one-token chunk exceeds {name} formatted-input limit: {current.id}")
                    midpoint = len(words) // 2
                    pieces = [" ".join(words[:midpoint]), " ".join(words[midpoint:])]
                    queue.extend(replace(current, text=piece, token_count=len(piece.split())) for piece in pieces)
            pending = fitted
        per_document: dict[str, int] = defaultdict(int)
        materialized: list[Chunk] = []
        for chunk in pending:
            ordinal = per_document[chunk.document_id]
            per_document[chunk.document_id] += 1
            content_hash = "sha256:" + hashlib.sha256(chunk.text.encode()).hexdigest()
            ident = hashlib.sha256(f"{chunk.document_id}:{ordinal}:{content_hash}".encode()).hexdigest()
            materialized.append(replace(chunk, id="chunk:" + ident, ordinal=ordinal, content_hash=content_hash))
        return materialized

    def index(self, *, providers: str | Sequence[str] = "local", batch_size: int | None = None) -> dict[str, Any]:
        selected = self._selected_providers(providers)
        nodes, edges, dangling = EstateGraphAdapter(self.config.resolve(self.config.raw["graph"]["path"])).load()
        chunks = self._fit_to_provider_budgets(scan_chunks(self.config), selected)
        source_receipt = self.store.replace_sources(self.config.raw["sources"], chunks)
        self.store.sync_graph(nodes, edges)
        receipts: list[dict[str, Any]] = []
        for name in selected:
            provider = self.providers[name]
            profile = provider.profile
            pending = self.store.pending_chunks(profile)
            job_id = self.store.start_job(profile, len(pending))
            completed = 0
            try:
                # How many texts one request may carry is a property of the MODEL and the
                # device, not of the caller. A batch of 16 real chunks takes ~8s on a 300m
                # model here and ~76s on a 0.6b one -- the second blows any timeout sized
                # for the first, and reads as a broken server rather than a slower model.
                size = int(self.config.raw["profiles"][name].get("embed_batch_size", batch_size or 16))
                for offset in range(0, len(pending), size):
                    batch = pending[offset : offset + size]
                    # Local formatting includes the heading title in the model text; Gemini uses
                    # its declared native RETRIEVAL_DOCUMENT task type for the same evidence.
                    texts = [f"{chunk.title}\n{chunk.text}" for chunk in batch]
                    vectors = provider.embed(texts, purpose="document")
                    self.store.save_embeddings(profile, batch, vectors)
                    completed += len(batch)
                    with self.store.conn:
                        self.store.conn.execute("UPDATE index_jobs SET outstanding=? WHERE id=?", (len(pending) - completed, job_id))
                self.store.finish_job(job_id)
                receipts.append({"provider": name, "status": "complete", "embedded": completed, "job_id": job_id})
            except Exception as exc:
                self.store.finish_job(job_id, error=str(exc))
                receipts.append({"provider": name, "status": "incomplete", "embedded": completed, "job_id": job_id, "error": str(exc)})
        return {"operation": "index", "sources": source_receipt, "graph": {"nodes": len(nodes), "edges": len(edges), "dangling_edges": dangling}, "providers": receipts, "status": self.store.status()}

    @staticmethod
    def _mode_names(mode: str) -> list[str]:
        if mode == "local":
            return ["local"]
        if mode == "cloud":
            return ["cloud"]
        if mode == "both":
            return ["local", "cloud"]
        if mode == "lexical":
            return []
        raise ConfigError("mode must be local, cloud, both, or lexical")

    def search(self, query: str, *, mode: str | None = None, rerank: bool = True, graph: bool = True) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ConfigError("query must be non-empty")
        mode = mode or self.config.raw["retrieval"]["default_mode"]
        names = self._mode_names(mode)
        retrieval = self.config.raw["retrieval"]
        limit = int(retrieval["candidate_limit"])
        degradation: list[dict[str, str]] = []
        exact = self.store.exact_rows(query, limit)
        lexical = self.store.lexical_rows(self.core, query, limit)
        lists: list[list[dict[str, Any]]] = [lexical]
        weights: list[float] = [float(retrieval["lexical_weight"])]
        labels: list[str] = ["lexical"]
        dense_lists: list[list[dict[str, Any]]] = []
        for name in names:
            provider = self.providers[name]
            try:
                purpose = "code_query" if any(token in query for token in ("::", ".py", "def ", "class ")) else "query"
                vector = provider.embed([query], purpose=purpose)[0]
                dense = self.store.dense_rows(provider.profile, vector, limit)
                if not dense:
                    degradation.append({"component": name, "reason": "matching_index_has_no_coverage"})
                dense_lists.append(dense)
            except ProviderError as exc:
                degradation.append({"component": name, "reason": str(exc)})
        seed_pool = exact + lexical + [item for dense in dense_lists for item in dense]
        if graph:
            graph_rows, dangling = expand_one_hop(
                self.store, seed_pool, max_seeds=int(self.config.raw["graph"]["max_seed_nodes"]),
                limit=int(self.config.raw["graph"]["max_expanded_candidates"]),
            )
            if graph_rows:
                lists.append(graph_rows)
                weights.append(float(retrieval["graph_weight"]))
                labels.append("graph")
            if dangling:
                degradation.append({"component": "graph", "reason": "dangling_edges:" + ",".join(dangling)})
        semantic_weight = float(retrieval["semantic_weight"]) / max(1, len(names))
        for name, dense in zip(names, dense_lists):
            if dense:
                lists.append(dense)
                weights.append(semantic_weight)
                labels.append("semantic:" + name)
        fused = self.core.rrf(lists, weights, labels, int(retrieval["rrf_k"])) if lists else []
        rows = {item["id"]: item for item in fused}
        for item in exact:
            rows.setdefault(item["id"], item)
        ordered = [rows[item["id"]] for item in fused] + [item for item in exact if item["id"] not in {row["id"] for row in fused}]
        stored_rows = self.store.rows_for_ids(item["id"] for item in ordered)
        ordered = [{**stored_rows.get(item["id"], {}), **item} for item in ordered]
        results = [row_to_result(row) for row in ordered]
        for result, row in zip(results, ordered):
            if "graph_edge" in row:
                result.graph_edge = row["graph_edge"]
            if "content_hash" in row:
                result.signals["content_hash"] = row["content_hash"]
        explicit = bool(exact) and ("/" in query or "." in query or "::" in query or query.startswith("chunk:"))
        if rerank and results:
            candidates = results[: int(retrieval["rerank_candidates"])]
            try:
                scores = self.reranker.rerank(query, [item.text for item in candidates])
                for item, score in zip(candidates, scores):
                    item.signals["reranker_score"] = score
                    item.score = score
                results = sorted(candidates, key=lambda item: (-item.score, item.id)) + results[len(candidates):]
            except ProviderError as exc:
                degradation.append({"component": "reranker", "reason": str(exc)})
        if explicit:
            exact_ids = {item["id"] for item in exact}
            preserved = [item for item in results if item.id in exact_ids]
            results = preserved + [item for item in results if item.id not in exact_ids]
        selected: list[SearchResult] = []
        per_parent: dict[str, int] = defaultdict(int)
        for result in results:
            if per_parent[result.parent_id] >= int(retrieval["per_document_limit"]):
                continue
            per_parent[result.parent_id] += 1
            selected.append(result)
            if len(selected) == int(retrieval["passage_limit"]):
                break
        for index, result in enumerate(selected, 1):
            result.citation_id = f"P{index:03d}"
        return {
            "operation": "search", "query": query, "mode": mode, "degraded": bool(degradation), "degradation": degradation,
            "coverage": self.store.status()["profiles"], "results": [item.receipt() for item in selected],
        }

    def _context_prompt(self, question: str, results: Sequence[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
        generator_limit = int(self.config.raw["services"]["generator"]["max_context_tokens"])
        reserve = int(self.config.raw["services"]["generator"]["max_output_tokens"])
        blocks: list[str] = []
        included: list[str] = []
        skipped: list[str] = []
        for result in results:
            block = "[{citation}] source={source} path={path}:{start}-{end}\n{text}".format(
                citation=result["citation_id"], source=result["source_id"], path=result["path"],
                start=result["line_start"], end=result["line_end"], text=result["text"],
            )
            candidate = "Question:\n" + question + "\n\nPassages:\n" + "\n\n".join(blocks + [block])
            if self.generator.count_tokens(_SYSTEM_PROMPT + "\n" + candidate) + reserve > generator_limit:
                skipped.append(result["citation_id"])
                continue
            blocks.append(block)
            included.append(result["citation_id"])
        return "Question:\n" + question + "\n\nPassages:\n" + "\n\n".join(blocks), included, skipped

    def ask(self, question: str, *, mode: str | None = None) -> dict[str, Any]:
        retrieved = self.search(question, mode=mode)
        if not retrieved["results"]:
            return {"operation": "ask", "status": "insufficient_evidence", "answer": None, "retrieval": retrieved}
        prompt, identifiers, skipped = self._context_prompt(question, retrieved["results"])
        if not identifiers:
            return {"operation": "ask", "status": "insufficient_evidence", "answer": None, "reason": "all_evidence_exceeds_context", "retrieval": retrieved}
        generated = self.generator.generate(prompt)
        citations = [item.strip() for group in _CITATION_RE.findall(generated["answer"]) for item in group.split(",")]
        unknown = sorted(set(citations) - set(identifiers))
        if not citations or unknown:
            return {"operation": "ask", "status": "unresolved_citations", "answer": None, "unknown_citations": unknown, "retrieval": retrieved, "generation": generated}
        return {"operation": "ask", "status": "ok", "answer": generated["answer"], "citations": citations, "context_passages": identifiers,
                "context_skipped": skipped, "retrieval": retrieved, "generation": {key: value for key, value in generated.items() if key != "answer"}}

    def status(self) -> dict[str, Any]:
        return {"operation": "status", "config_hash": self.config.config_hash, **self.store.status()}

    def doctor(self) -> dict[str, Any]:
        errors = validate_config(self.config)
        checks: dict[str, Any] = {
            "configuration": {"status": "pass" if not errors else "fail", "errors": errors},
            "declared_core": self.core.verify_identity(),
            "local_embedding": self.providers["local"].health(),
            "cloud_embedding": self.providers["cloud"].health(),
            "reranker": self.reranker.health(), "generator": self.generator.health(),
            "limits": {"embedder_context": self.config.raw["profiles"]["local"]["max_input_tokens"], "generator_context": self.config.raw["services"]["generator"]["max_context_tokens"]},
        }
        return {"operation": "doctor", "healthy": not errors and all(
            check.get("healthy", True) for name, check in checks.items() if name not in {"configuration", "declared_core", "limits"}
        ), "checks": checks}

    def check(self) -> dict[str, Any]:
        lint_errors = validate_config(self.config)
        identity: dict[str, Any]
        try:
            identity = {"status": "pass", "evidence": self.core.verify_identity()}
        except Exception as exc:
            identity = {"status": "fail", "error": str(exc)}
        return {
            "operation": "check",
            "qualified_release": False,
            "checks": [
                {"id": "NLKE-01", "level": "lint", "status": "pass" if not lint_errors else "fail", "evidence": lint_errors},
                {"id": "NLKE-02", "level": "gate", **identity},
                {"id": "NLKE-07", "level": "review", "status": "vacuous", "reason": "no independently authored blind evaluation receipt supplied"},
            ],
            "status": self.store.status(),
        }
