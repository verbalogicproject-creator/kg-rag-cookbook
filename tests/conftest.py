"""Shared test fixtures for nlke_hybrid.

The canonical `declared_core` location is resolved from `hybrid-rag.json` the
same way production resolves it, rather than hardcoded. Two test modules used to
open `Path("/root/projects/declared_core")` directly, which meant the suite —
like the package itself — only ran on the machine that path exists on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "hybrid-rag.json"


def canonical_declared_core() -> Path:
    """Where this checkout expects its `declared_core` sibling to be.

    Single source of truth: `hybrid-rag.json`'s `canonical_dependency.path`,
    resolved against the config's own directory — identical to
    `HybridConfig.resolve`, which treats a relative path as relative to the
    config file. A test that hardcodes the absolute path can pass while the
    shipped config points somewhere else entirely.
    """
    declared = json.loads(CONFIG_PATH.read_text())["canonical_dependency"]["path"]
    path = Path(declared)
    return path if path.is_absolute() else (CONFIG_PATH.parent / path).resolve()


@pytest.fixture(scope="session")
def canonical_core() -> Path:
    path = canonical_declared_core()
    if not path.is_dir():
        pytest.skip(f"declared_core sibling checkout not present at {path}")
    return path
