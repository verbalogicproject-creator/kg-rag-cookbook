from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class EmbeddingProfile:
    name: str
    provider: str
    model: str
    dimensions: int
    normalization: str
    formatting: dict[str, str]

    def identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dimensions": self.dimensions,
            "normalization": self.normalization,
            "formatting": self.formatting,
        }


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    source_id: str
    path: str
    ordinal: int
    content_hash: str
    text: str
    title: str
    symbol: str | None
    line_start: int
    line_end: int
    token_count: int
    cloud_eligible: bool


@dataclass
class SearchResult:
    id: str
    source_id: str
    parent_id: str
    path: str
    line_start: int | None
    line_end: int | None
    text: str
    title: str
    symbol: str | None = None
    score: float = 0.0
    signals: dict[str, Any] = field(default_factory=dict)
    citation_id: str | None = None
    graph_edge: dict[str, Any] | None = None

    def receipt(self) -> dict[str, Any]:
        data = asdict(self)
        data["citation_location"] = {
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }
        return data


class EmbeddingProvider(ABC):
    profile: EmbeddingProfile

    @abstractmethod
    def embed(self, texts: Sequence[str], *, purpose: str) -> list[np.ndarray]:
        """Embed texts in request order, validating the declared profile."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count a fully formatted input using the provider's facility."""

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return a non-secret service observation."""


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        """Return one score per document in the supplied order."""


class Generator(ABC):
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count a complete generation prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> dict[str, Any]:
        """Return a non-streamed answer and provider usage metadata."""
