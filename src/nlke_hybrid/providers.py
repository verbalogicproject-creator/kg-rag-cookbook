from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Sequence

import httpx
import numpy as np

from .config import HybridConfig
from .errors import ContextOverflow, ProviderError
from .models import EmbeddingProfile, EmbeddingProvider, Generator, Reranker

LOCAL_INFERENCE_LOCK = threading.Lock()


def _retry(call: Callable[[], Any], attempts: int) -> Any:
    last: Exception | None = None
    for attempt in range(attempts + 1):
        try:
            return call()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {400, 401, 403, 404, 422} or attempt == attempts:
                raise ProviderError(f"HTTP {status}: {exc.response.text[:300]}") from exc
            last = exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == attempts:
                raise ProviderError(f"transient HTTP failure after {attempts + 1} attempts: {exc}") from exc
            last = exc
        time.sleep(0.2 * (attempt + 1))
    raise ProviderError(str(last))


def _models_observation(client: httpx.Client, endpoint: str, expected: str) -> dict[str, Any]:
    response = client.get(endpoint)
    response.raise_for_status()
    body = response.json()
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ProviderError("models response has no data list")
    ids = [row.get("id") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)]
    match = next((row for row in rows if isinstance(row, dict) and row.get("id") == expected), None)
    meta = match.get("meta", {}) if isinstance(match, dict) else {}
    return {
        "model_identity": {"expected": expected, "observed": ids, "matches": match is not None},
        "response_shape": "valid",
        "context_tokens": meta.get("n_ctx"),
    }


class LocalHTTPEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: HybridConfig):
        self.config = config
        self.raw = config.raw["profiles"]["local"]
        self.profile = config.profile("local")
        # Declared per profile, because how long an embedder takes is a property of the
        # MODEL, not of the client. 30s is fine for a 300m model and too short for a 0.6b
        # one on this device -- which surfaced as "transient HTTP failure after 3 attempts:
        # timed out" partway through an index run, i.e. a slow model looking like a broken
        # one. Default preserved so existing configs behave identically.
        self.timeout = float(self.raw.get("request_timeout_seconds", 30.0))

    def format(self, text: str, *, purpose: str, title: str = "") -> str:
        template = self.raw["document_format"] if purpose == "document" else self.raw["query_format"]
        return template.format(title=title, text=text)

    def count_tokens(self, text: str) -> int:
        endpoint = self.raw["tokenize_endpoint"]
        def call() -> int:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(endpoint, json={"content": text})
                response.raise_for_status()
                payload = response.json()
            tokens = payload.get("tokens") if isinstance(payload, dict) else None
            if isinstance(tokens, list):
                return len(tokens)
            if isinstance(payload, dict) and isinstance(payload.get("count"), int):
                return payload["count"]
            raise ProviderError("local tokenizer response has neither tokens nor count")
        return _retry(call, int(self.config.raw["enforcement"]["retry_attempts"]))

    def embed(self, texts: Sequence[str], *, purpose: str) -> list[np.ndarray]:
        formatted = [self.format(text, purpose=purpose) for text in texts]
        if any(self.count_tokens(text) > int(self.raw["max_input_tokens"]) for text in formatted):
            raise ContextOverflow("formatted local embedding input exceeds declared token limit")
        def call() -> list[np.ndarray]:
            with LOCAL_INFERENCE_LOCK, httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.raw["endpoint"], json={"model": self.profile.model, "input": formatted})
                response.raise_for_status()
                payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list) or len(data) != len(texts):
                raise ProviderError("local embedding response count does not match request")
            indexed: list[tuple[int, np.ndarray]] = []
            for position, row in enumerate(data):
                if not isinstance(row, dict) or not isinstance(row.get("embedding"), list):
                    raise ProviderError("local embedding response is malformed")
                index = row.get("index", position)
                if not isinstance(index, int):
                    raise ProviderError("local embedding response index is malformed")
                indexed.append((index, np.asarray(row["embedding"], dtype=np.float32)))
            if sorted(index for index, _ in indexed) != list(range(len(texts))):
                raise ProviderError("local embedding response indexes do not cover request order")
            return [vector for _, vector in sorted(indexed)]
        return _retry(call, int(self.config.raw["enforcement"]["retry_attempts"]))

    def health(self) -> dict[str, Any]:
        out: dict[str, Any] = {"provider": "local", "endpoint": self.raw["health_endpoint"]}
        try:
            models_endpoint = self.raw["endpoint"].rsplit("/v1/embeddings", 1)[0] + "/v1/models"
            with httpx.Client(timeout=3.0) as client:
                response = client.get(self.raw["health_endpoint"])
                out.update(_models_observation(client, models_endpoint, self.profile.model))
            token_count = self.count_tokens(self.format("NLKE tokenizer probe", purpose="query"))
            out["tokenizer"] = {"available": True, "probe_count": token_count}
            out["healthy"] = response.is_success and out["model_identity"]["matches"]
            out["status_code"] = response.status_code
        except (httpx.HTTPError, ProviderError) as exc:
            out.update({"healthy": False, "tokenizer": {"available": False}, "error": str(exc)})
        return out


class GeminiEmbeddingProvider(EmbeddingProvider):
    # Token counting and embedding share Gemini's request quota. A fixed, bounded
    # pacing interval keeps a full declared corpus below the observed free-tier
    # per-minute limit without relying on a server to reject work first.
    _rate_lock = threading.Lock()
    _next_request_at = 0.0
    _request_interval_seconds = 0.67

    def __init__(self, config: HybridConfig):
        self.config = config
        self.raw = config.raw["profiles"]["cloud"]
        self.profile = config.profile("cloud")
        self._client: Any | None = None

    def _client_instance(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise ProviderError("google-genai is not installed") from exc
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ProviderError("GEMINI_API_KEY or GOOGLE_API_KEY is required for cloud retrieval")
            self._client = genai.Client(api_key=api_key)
        return self._client

    @classmethod
    def _pace_request(cls) -> None:
        with cls._rate_lock:
            now = time.monotonic()
            wait = max(0.0, cls._next_request_at - now)
            cls._next_request_at = max(now, cls._next_request_at) + cls._request_interval_seconds
        if wait:
            time.sleep(wait)

    def _task_type(self, purpose: str) -> str:
        if purpose == "document":
            return self.raw["document_task_type"]
        if purpose == "code_query":
            return self.raw["code_query_task_type"]
        return self.raw["query_task_type"]

    def count_tokens(self, text: str) -> int:
        client = self._client_instance()
        try:
            self._pace_request()
            response = client.models.count_tokens(model=self.profile.model, contents=text)
            total = getattr(response, "total_tokens", None)
            if not isinstance(total, int):
                raise ProviderError("Gemini count_tokens response has no total_tokens")
            return total
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Gemini token counting failed: {exc}") from exc

    def embed(self, texts: Sequence[str], *, purpose: str) -> list[np.ndarray]:
        client = self._client_instance()
        task_type = self._task_type(purpose)
        last_error: ProviderError | None = None
        for attempt in range(int(self.config.raw["enforcement"]["retry_attempts"]) + 1):
            try:
                from google.genai import types
                request_config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.profile.dimensions)
                self._pace_request()
                response = client.models.embed_content(model=self.profile.model, contents=list(texts), config=request_config)
                embeddings = getattr(response, "embeddings", None)
                if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                    raise ProviderError("Gemini embedding response count does not match request")
                vectors = [np.asarray(getattr(item, "values", None), dtype=np.float32) for item in embeddings]
                if any(vector.ndim != 1 or vector.shape[0] != self.profile.dimensions for vector in vectors):
                    raise ProviderError("Gemini embedding response does not match declared dimensions")
                return vectors
            except ProviderError:
                raise
            except Exception as exc:
                last_error = ProviderError(f"Gemini embedding failed: {exc}")
                transient = any(marker in str(exc).upper() for marker in ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "UNAVAILABLE", "TIMEOUT"))
                if not transient or attempt == int(self.config.raw["enforcement"]["retry_attempts"]):
                    raise last_error from exc
                time.sleep(min(8.0, 2.0 ** attempt))
        raise last_error or ProviderError("Gemini embedding failed")

    def health(self) -> dict[str, Any]:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return {"provider": "cloud", "healthy": False, "reason": "credential_unavailable"}
        try:
            count = self.count_tokens("NLKE tokenizer probe")
            return {"provider": "cloud", "healthy": True, "tokenizer": {"available": True, "probe_count": count}}
        except ProviderError as exc:
            return {"provider": "cloud", "healthy": False, "error": str(exc)}


class BGEReranker(Reranker):
    def __init__(self, config: HybridConfig):
        self.raw = config.raw["services"]["reranker"]
        self.attempts = int(config.raw["enforcement"]["retry_attempts"])

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        def call() -> list[float]:
            with LOCAL_INFERENCE_LOCK, httpx.Client(timeout=30.0) as client:
                response = client.post(self.raw["endpoint"], json={"model": self.raw["model"], "query": query, "documents": list(documents)})
                response.raise_for_status()
                payload = response.json()
            rows = payload.get("results", payload.get("data")) if isinstance(payload, dict) else None
            if not isinstance(rows, list) or len(rows) != len(documents):
                raise ProviderError("reranker response count does not match request")
            indexed: list[tuple[int, float]] = []
            for fallback, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ProviderError("reranker response is malformed")
                index = row.get("index", fallback)
                score = row.get("relevance_score", row.get("score"))
                if not isinstance(index, int) or not isinstance(score, (int, float)):
                    raise ProviderError("reranker response lacks index or score")
                indexed.append((index, float(score)))
            if sorted(index for index, _ in indexed) != list(range(len(documents))):
                raise ProviderError("reranker response indexes do not cover request order")
            return [score for _, score in sorted(indexed)]
        return _retry(call, self.attempts)

    def health(self) -> dict[str, Any]:
        try:
            models_endpoint = self.raw["endpoint"].rsplit("/v1/rerank", 1)[0] + "/v1/models"
            with httpx.Client(timeout=3.0) as client:
                response = client.get(self.raw["health_endpoint"])
                observed = _models_observation(client, models_endpoint, self.raw["model"])
            return {"healthy": response.is_success and observed["model_identity"]["matches"], "status_code": response.status_code, "endpoint": self.raw["health_endpoint"], **observed}
        except (httpx.HTTPError, ProviderError) as exc:
            return {"healthy": False, "endpoint": self.raw["health_endpoint"], "error": str(exc)}


class QwenGenerator(Generator):
    def __init__(self, config: HybridConfig):
        self.raw = config.raw["services"]["generator"]

    def count_tokens(self, text: str) -> int:
        token_endpoint = self.raw["endpoint"].replace("/v1/chat/completions", "/tokenize")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(token_endpoint, json={"content": text})
                response.raise_for_status()
                body = response.json()
            if isinstance(body.get("tokens"), list):
                return len(body["tokens"])
            if isinstance(body.get("count"), int):
                return body["count"]
        except httpx.HTTPError as exc:
            raise ProviderError(f"generator tokenizer is unavailable: {exc}") from exc
        raise ProviderError("generator tokenizer response has neither tokens nor count")

    def generate(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.raw["model"],
            "messages": [
                {"role": "system", "content": "Answer only from supplied passages. Cite every factual claim with one or more passage IDs in square brackets."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.raw["temperature"], "top_p": self.raw["top_p"], "top_k": self.raw["top_k"],
            "max_tokens": self.raw["max_output_tokens"], "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            with LOCAL_INFERENCE_LOCK, httpx.Client(timeout=120.0) as client:
                response = client.post(self.raw["endpoint"], json=payload)
                response.raise_for_status()
                body = response.json()
            answer = body["choices"][0]["message"]["content"]
            if not isinstance(answer, str):
                raise ProviderError("generator response content is not text")
            return {"answer": answer, "usage": body.get("usage", {}), "model": body.get("model"), "finish_reason": body["choices"][0].get("finish_reason"), "settings": {key: payload[key] for key in ("temperature", "top_p", "top_k", "max_tokens")}}
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"generation failed: {exc}") from exc

    def health(self) -> dict[str, Any]:
        try:
            models_endpoint = self.raw["endpoint"].rsplit("/v1/chat/completions", 1)[0] + "/v1/models"
            with httpx.Client(timeout=3.0) as client:
                response = client.get(self.raw["health_endpoint"])
                observed = _models_observation(client, models_endpoint, self.raw["model"])
            return {"healthy": response.is_success and observed["model_identity"]["matches"], "status_code": response.status_code, "endpoint": self.raw["health_endpoint"], **observed}
        except (httpx.HTTPError, ProviderError) as exc:
            return {"healthy": False, "endpoint": self.raw["health_endpoint"], "error": str(exc)}
