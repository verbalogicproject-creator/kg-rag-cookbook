"""Strict adapter for the canonical declared_core sibling package."""

from __future__ import annotations

import hashlib
import importlib
import subprocess
from pathlib import Path
from typing import Any

from .config import HybridConfig
from .errors import IdentityError


def _tree_sha256(root: Path) -> str:
    lines: list[bytes] = []
    for path in sorted((root / "declared_core").rglob("*.py")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path}\n".encode())
    return hashlib.sha256(b"".join(lines)).hexdigest()


class DeclaredCoreAdapter:
    """Use BM25 and RRF from exactly one declared, checked copy."""

    def __init__(self, config: HybridConfig):
        self.config = config
        self._loaded = False

    def verify_identity(self) -> dict[str, str]:
        dependency = self.config.raw["canonical_dependency"]
        root = self.config.resolve(dependency["path"])
        try:
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                capture_output=True, text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise IdentityError(f"cannot read declared-core revision at {root}") from exc
        tree = _tree_sha256(root)
        if revision != dependency["revision"] or tree != dependency["tree_sha256"]:
            raise IdentityError(
                "canonical declared-core identity differs from hybrid-rag.json "
                f"(revision={revision}, tree_sha256={tree})"
            )
        return {"revision": revision, "tree_sha256": tree, "path": str(root)}

    def _imports(self) -> tuple[Any, Any, Any]:
        if not self._loaded:
            self.verify_identity()
            expected = self.config.resolve(self.config.raw["canonical_dependency"]["path"])
            try:
                package = importlib.import_module("declared_core")
                bm25 = importlib.import_module("declared_core.retrieval.bm25")
                rrf = importlib.import_module("declared_core.retrieval.rrf")
                schema = importlib.import_module("declared_core.schema")
            except ImportError as exc:
                # Name the mechanism, not just the absence. The obvious reading of
                # "install it" is `pip install -e`, which under PEP 660 puts an
                # editable *proxy* on the path — `__file__` then resolves into
                # site-packages and the canonicality check below rejects it. An
                # error whose natural next step is a second error is not a fix.
                raise IdentityError(
                    f"declared-core is not importable. It is a sibling working copy, not a "
                    f"pip package: put {expected} on sys.path, e.g. write that one line into "
                    f"<venv>/lib/python*/site-packages/declared_core_canonical.pth. "
                    f"`pip install -e` installs a PEP 660 proxy whose __file__ is not canonical "
                    f"and will be refused."
                ) from exc
            loaded = Path(package.__file__ or "").resolve()
            if expected not in loaded.parents:
                raise IdentityError(
                    f"loaded declared_core is not canonical: {loaded} is not under {expected}. "
                    f"A PEP 660 editable install produces exactly this; use a .pth file holding "
                    f"{expected} instead."
                )
            self._bm25, self._rrf, self._schema = bm25, rrf, schema
            self._loaded = True
        return self._bm25, self._rrf, self._schema

    def lexical(self, conn: Any, query: str, limit: int) -> list[dict[str, Any]]:
        bm25, _, schema = self._imports()
        source = schema.SourceTable(
            "chunks", id_column="id", text_columns=("title", "symbol", "text"),
            carry_columns=("document_id", "source_id", "path", "line_start", "line_end"),
            fts_table="chunks_fts",
        )
        return bm25.bm25_source(conn, source, query, limit=limit)

    def rrf(self, ranked_lists: list[list[dict[str, Any]]], weights: list[float], labels: list[str], k: int) -> list[dict[str, Any]]:
        _, rrf, _ = self._imports()
        fused = rrf.rrf_fuse(ranked_lists, weights=weights, labels=labels, k=k)
        return sorted(fused, key=lambda item: (-float(item["rrf_score"]), str(item["id"])))
