"""This project must be installable somewhere other than the machine that wrote it.

It was not. `git ls-files` returned 15 files while `src/`, `tests/`, `pyproject.toml`
and `docs/` sat untracked, so there was nothing to install *from* anywhere else —
and once that was fixed, `pyproject.toml` still declared
`declared-core @ file:///root/projects/declared_core`: an absolute path that
exists on one machine, for a repository that is private, so neither the path nor
a `git+https://` URL would resolve elsewhere.

These tests fail if either regression returns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Roots that exist only on the authoring device. `/storage/emulated` and the
#: Termux prefix are included because this estate spans three filesystems and a
#: path from any of them is equally unportable.
MACHINE_ROOTS = re.compile(r"(?:file://)?/(?:root|home/[^/\s\"]+)/|/data/data/com\.termux|/storage/emulated")


def test_pyproject_declares_no_machine_specific_dependency():
    """A dependency pinned to an absolute path installs on exactly one computer."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    # Only the dependency tables matter; prose in comments may legitimately cite
    # a path while explaining why it is not a dependency.
    in_deps, offenders = False, []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("dependencies") or stripped.startswith("dev ="):
            in_deps = True
        if in_deps and MACHINE_ROOTS.search(stripped):
            offenders.append(stripped)
        if in_deps and stripped == "]":
            in_deps = False
    assert not offenders, f"machine-specific dependency: {offenders}"


def test_canonical_dependency_path_is_relative():
    """`hybrid-rag.json` locates its sibling relative to itself.

    `HybridConfig.resolve` already resolves a relative path against the config's
    own directory, so a relative value works from any checkout location while an
    absolute one silently binds the config to one machine.
    """
    declared = json.loads((REPO_ROOT / "hybrid-rag.json").read_text())
    path = declared["canonical_dependency"]["path"]
    assert not Path(path).is_absolute(), (
        f"canonical_dependency.path is absolute ({path}); use a path relative to "
        "hybrid-rag.json so the config travels with the checkout")


def test_the_pinned_sibling_is_still_identified_by_revision_and_tree_hash():
    """Relative does not mean unpinned.

    Making the path portable must not weaken the identity check: the sibling is
    still nailed to a specific revision and content hash, which is what lets
    `declared_core.py` refuse a copy it cannot vouch for.
    """
    declared = json.loads((REPO_ROOT / "hybrid-rag.json").read_text())["canonical_dependency"]
    assert re.fullmatch(r"[0-9a-f]{40}", declared["revision"]), declared["revision"]
    assert re.fullmatch(r"[0-9a-f]{64}", declared["tree_sha256"]), declared["tree_sha256"]


def test_the_package_itself_is_tracked():
    """The original defect: the code existed and git had never been told."""
    import subprocess

    tracked = set(subprocess.check_output(
        ["git", "ls-files"], cwd=REPO_ROOT, text=True).split())
    for required in ("pyproject.toml", "hybrid-rag.json",
                     "src/nlke_hybrid/__init__.py", "src/nlke_hybrid/declared_core.py"):
        assert required in tracked, f"{required} is not tracked; a clone would not have it"
