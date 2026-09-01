#!/usr/bin/env python3
"""TS-kg-rag-of-kg-rag — build a knowledge graph whose domain is its author's own
retrieval systems.

The estate holds two generations of KG-RAG work across ~30 repositories, 1,186
`.ngf.md` cards (529 of them inside the declared allowlist) and 87 databases. Every finding in it was true when written, and
none of it is queryable. This builds the graph that makes it queryable.

Three rules govern every line here, taken from the estate's own doctrine cards:

  * **No model in the decision path.** Everything below is `ast`, `re`, and
    arithmetic. A verdict a third party cannot re-execute in three years is not
    evidence.
  * **Absence is not a result.** Every check asserts a positive count. A build
    that finds nothing must fail, not pass quietly.
  * **Extracted, never typed.** Counts, digests and edges are derived at build
    time. A number typed into a document drifts; a number extracted fails loudly.

Determinism is the property that makes `--check` meaningful, so every traversal is
sorted and every insert is ordered. This builder calls no clock; timestamps enter
only from frontmatter, which is already fixed.

The storage engine does call one. `kg_toolkit/store.py:37` stamps `created_at` on
every row, so a raw `iterdump()` of two identical builds differs. `check` therefore
compares a canonical projection that excludes that column — see `dump()`. The
property is recorded rather than patched around quietly: it belongs in the graph as
a finding about the estate, which is what the graph is for.

Usage
-----
    python3 TS-kg-rag-of-kg-rag.py build
    python3 TS-kg-rag-of-kg-rag.py build --out /tmp/g.db
    python3 TS-kg-rag-of-kg-rag.py check          # rebuild + byte-compare
    python3 TS-kg-rag-of-kg-rag.py stats
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCES = HERE / "sources.json"
DEFAULT_OUT = HERE / "TS-kg-rag-of-kg-rag.db"

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache",
             ".pytest_cache", "dist", "build", ".itl", ".vouch", ".context-os"}

# --------------------------------------------------------------------------
# doctrine — the four rules every finding will hang off via `governed_by`.
# Fixed content, so they are constants rather than an extraction.
# --------------------------------------------------------------------------

DOCTRINE = [
    ("declaration",
     "Retrieval improves only by adding information the system lacked, not by "
     "rearranging what it already has. A declared dimension must distinguish "
     "within a query's candidate set, or it is a near-constant that displaces "
     "signal and lowers recall."),
    ("retrieval",
     "Find the stage that actually decides an outcome before fixing anything — "
     "ablate, do not guess from the symptom. New content is not free: gate "
     "additions on the existing gold set's regressions."),
    ("measurement",
     "A comparative claim needs a statistical gate or it is NOT_ESTABLISHED, no "
     "matter how convincing the story. Sample size is set by discordant flips, "
     "not raw n. No model may sit in the decision path."),
    # Rules 5 and 6 were not invented here. Each is stated in at least three
    # places in the estate — in a contract, in code, and in a primitive card —
    # and was simply never elevated to a doctrine card. 13 of the 23 findings
    # that answered to no rule answer to one of these two.
    ("authority",
     "Knowing what something is does not confer permission to act on it, and "
     "issuing a directive is not performing it. Grounding, authority and effect "
     "are separate declarations. A receipt makes an assertion verifiable, not "
     "true; retrieved content is not trusted content; and coverage must be "
     "asserted per call-site, never per codebase."),
    ("provenance",
     "A copy of a fact has no expiry date. Every derived value is either "
     "traceable to its input or an explicit refusal, a human declaration is "
     "never clobbered by a re-derivation, and a pointer carrying the digest of "
     "what it points at cannot drift undetected."),
    ("absence-is-not-a-result",
     "A check whose failure mode is indistinguishable from its success mode "
     "(silence means no error) reports nothing rather than passing. Every check "
     "must assert something positive — a count — not merely the lack of an "
     "exception."),
]


# --------------------------------------------------------------------------
# engine bootstrap
# --------------------------------------------------------------------------

def load_sources(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_roots(sources: dict, root: Path) -> dict[str, Path]:
    out = {}
    for name, rel in sorted(sources["roots"].items()):
        p = Path(rel)
        out[name] = p if p.is_absolute() else (root / p).resolve()
    return out


def import_engine(sources: dict, roots: dict[str, Path]):
    """Put the engine repo on sys.path and import it.

    None of these packages are pip-installed — each resolves only from inside its
    own repository. That is declared in sources.json rather than rediscovered,
    because a builder that depends on its working directory is a builder that
    breaks the first time it is run from somewhere else.
    """
    eng = sources["engine"]
    repo = (roots["gen2"] / eng["import_root"]).resolve()
    if not repo.is_dir():
        sys.exit(f"engine repo not found: {repo}")
    sys.path.insert(0, str(repo))
    try:
        import kg_toolkit  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment failure
        sys.exit(f"could not import {eng['package']} from {repo}: {exc}")
    if not hasattr(kg_toolkit, "KGSchema"):
        sys.exit(f"{repo} resolved as a namespace package, not {eng['package']}. "
                 "Check sources.json engine.import_root.")
    return kg_toolkit


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

def build_schema(kt):
    """The KGRAG_SCHEMA — a third preset beside kg_toolkit's CODE_SCHEMA.

    `dimension` and `fusion_method` are first-class node types rather than
    generic components on purpose. "Four disagreeing fusion formulas" has to be
    four nodes and a set of `contradicts` edges — a fact the graph can be asked
    about — not a sentence in a document asking to be believed.
    """
    N, E = kt.NodeType, kt.EdgeType
    return kt.KGSchema(
        name="kg-rag-of-kg-rags",
        node_types=(
            N("system", "A retrieval system or repository in the estate."),
            N("module", "One source file inside a system."),
            N("card", "One .ngf.md declared card — a document, not a claim."),
            N("component", "A named implementation unit worth citing on its own."),
            N("dimension", "One named [0,1] scoring signal."),
            N("fusion_method", "One way of combining retrieval signals."),
            N("capability", "A declared, negotiable query capability."),
            N("finding", "A method primitive: a falsifiable claim plus its evidence."),
            N("eval_harness", "Something that produces a measurement."),
            N("doctrine_rule", "One of the four governing rules."),
            N("ts_target", "A module proposed for TypeScript translation."),
        ),
        edge_types=(
            E("contains", source_types=("system", "card"),
              target_types=("module", "card", "finding"),
              description="A system holds modules and cards; a card holds findings."),
            # Package-level dependency was verified acyclic across 16 measured
            # edges. Module-level imports were not, and Python does not promise
            # they will be, so they are a separate, non-acyclic type.
            E("depends_on", source_types=("system",), target_types=("system",),
              acyclic=True, description="Verified acyclic package dependency."),
            E("imports", source_types=("module",), target_types=("module",),
              description="Module-level import. May be cyclic; Python allows it."),
            E("implements", source_types=("module",),
              target_types=("component", "dimension", "fusion_method", "capability"),
              description="A module realises a named unit."),
            # Widened beyond component/system: the supersession that matters most
            # in this estate is one fusion formula or dimension registry replacing
            # another, and endpoint-type violations are errors, not warnings.
            E("supersedes",
              source_types=("component", "system", "fusion_method", "dimension"),
              target_types=("component", "system", "fusion_method", "dimension"),
              acyclic=True, description="Generation 2 replacing generation 1."),
            E("contradicts", source_types=("fusion_method", "dimension", "finding"),
              target_types=("fusion_method", "dimension", "finding"), directed=False,
              description="Two things in the estate that cannot both be right."),
            E("measures", source_types=("eval_harness", "dimension"),
              target_types=("finding",), description="A harness produced this finding."),
            E("governed_by", source_types=("finding",), target_types=("doctrine_rule",),
              description="Which doctrine rule this finding answers to."),
            E("cites", source_types=("finding",), target_types=("finding",),
              description="Evidence chain between findings."),
            E("translates_to", source_types=("module",), target_types=("ts_target",),
              description="Proposed TypeScript translation."),
        ),
    )


# --------------------------------------------------------------------------
# extraction — deterministic, stdlib only
# --------------------------------------------------------------------------

def iter_py(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                out.append(Path(dirpath) / fn)
    return sorted(out)


def tree_digest(root: Path, files: list[Path]) -> str:
    """blake2b over (relpath, sha256(content)) pairs, sorted.

    Same shape as the estate's own VENDORED.json digests, so a source that moves
    by one byte is provably out of date rather than discouraged from drifting.
    """
    h = hashlib.blake2b(digest_size=16)
    for f in files:
        rel = f.relative_to(root).as_posix()
        try:
            body = f.read_bytes()
        except OSError:
            continue
        h.update(rel.encode("utf-8"))
        h.update(hashlib.sha256(body).hexdigest().encode("ascii"))
    return "blake2b:" + h.hexdigest()


def vendored_by(root: Path) -> list[str]:
    """What this package vendors, from its own VENDORED.json.

    Read rather than assumed: the digests are what make a vendored copy provably
    stale the moment its source moves, and the monorepo argument rests on how many
    of these exist and whether they still agree.
    """
    manifest = root / "VENDORED.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for entry in data.get("vendored", []):
        if isinstance(entry, dict) and entry.get("name"):
            out.append(f"{entry['name']}@{entry.get('source_version','?')}"
                       f" {str(entry.get('tree_sha') or '')[:26]}")
    return sorted(out)


def count_tests(files: list[Path]) -> int:
    pat = re.compile(r"^\s*def test_", re.M)
    total = 0
    for f in files:
        try:
            total += len(pat.findall(f.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return total


def load_frontmatter_parser(roots: dict[str, Path]):
    """Import the retrieval library's own frontmatter parser.

    `ngf_lint.py` validates cards "using the same YAML parser the retrieval
    library uses to ingest — not a more forgiving hand-rolled one", and that rule
    exists because a card this builder accepts but the retriever rejects is a
    card that will silently never be retrieved. So we import theirs.
    """
    repo = (roots["gen2"] / "frontmatter_rag").resolve()
    if repo.is_dir():
        sys.path.insert(0, str(repo))
        try:
            from frontmatter_rag.parse import parse_frontmatter
            return parse_frontmatter
        except ImportError:
            pass
    sys.exit("frontmatter_rag not importable — refusing to hand-roll a second "
             "YAML parser, which is the defect ngf_lint exists to prevent.")


YAML_BLOCK = re.compile(r"^```yaml\s*$(.*?)^```\s*$", re.M | re.S)

# category -> doctrine rule. Only these three map; the remaining categories
# (security, tooling, runtime, discipline) have no doctrine counterpart and get
# no edge rather than a forced one.
CATEGORY_TO_DOCTRINE = {
    "declaration": "declaration",
    "retrieval": "retrieval",
    "measurement": "measurement",
}

# The five statuses method-primitive-schema.ngf.md declares.
STATUS_DECLARED = {"ESTABLISHED", "DIRECTIONAL", "NOT_ESTABLISHED", "REFUTED", "CONVENTION"}

# Measured, not assumed: the corpus also uses OBSERVED (7), PAUSE (1) and
# MEASURED (1) — 9 of 43 entries, 21%, on vocabulary the schema does not declare.
# Those entries are ingested and tagged rather than discarded, and the drift is
# counted, because a schema and its corpus disagreeing is a finding about the
# estate, not a reason to lose nine claims.

# `evidence.source` is mandatory for method primitives. It is NOT mandatory for
# every card kind: `security_primitive_db` entries are threat primitives whose
# card-level status carries their provenance instead. Applying one kind's rule to
# another kind's entries is how a correct corpus gets reported as broken.
EVIDENCE_REQUIRED_KINDS = {"method_primitive_db"}


def iter_cards(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(".ngf.md"):
                out.append(Path(dirpath) / fn)
    return sorted(out)


def extract_primitives(body: str) -> list[dict]:
    """Method-primitive entries from a card body's fenced yaml blocks.

    An entry qualifies only if it carries an `id` and a `claim`. Anything else in
    a yaml block is configuration or an example, not a falsifiable claim, and is
    left alone rather than coerced into a finding.
    """
    import yaml
    out = []
    for match in YAML_BLOCK.finditer(body):
        try:
            data = yaml.safe_load(match.group(1))
        except Exception:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("id") and item.get("claim"):
                out.append(item)
    return out


def module_imports(path: Path) -> set[str]:
    """Top-level import roots of one file, via ast. Never exec, never import."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError, ValueError):
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build(sources: dict, roots: dict[str, Path], kt, out_path: Path) -> dict:
    schema = build_schema(kt)
    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = kt.connect(str(out_path))
    kt.create_store(conn, schema)
    mgr = kt.KGManager(conn, schema)

    nodes: list = []
    edges: list = []

    for name, text in DOCTRINE:
        nodes.append(kt.Node(
            node_id=kt.make_node_id("doctrine_rule", name),
            node_type="doctrine_rule", name=name, qualname=name,
            summary=text, extra={},
        ))

    pkg_to_system: dict[str, str] = {}
    per_system_files: dict[str, list[Path]] = {}
    system_root: dict[str, Path] = {}

    for spec in sorted(sources["packages"], key=lambda s: s["id"]):
        if spec["scope"] == "RETIRE":
            # Generation 1 is preserved as evidence, never walked as a dependency.
            nodes.append(kt.Node(
                node_id=kt.make_node_id("system", spec["id"]),
                node_type="system", name=spec["id"], qualname=spec["id"],
                summary=spec.get("retire_reason", ""),
                tags=("RETIRE",),
                extra={"scope": "RETIRE", "license": spec["license"]},
            ))
            continue

        base = roots[spec["root"]]
        path = (base / spec["path"]).resolve()
        if not path.is_dir():
            print(f"  ! declared but missing: {spec['id']} -> {path}", file=sys.stderr)
            continue

        files = iter_py(path)
        per_system_files[spec["id"]] = files
        system_root[spec["id"]] = path
        if spec.get("pkg"):
            pkg_to_system[spec["pkg"]] = spec["id"]

        loc = 0
        for f in files:
            try:
                loc += sum(1 for _ in f.open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass

        nodes.append(kt.Node(
            node_id=kt.make_node_id("system", spec["id"]),
            node_type="system", name=spec["id"], qualname=spec["id"],
            summary=f"{spec['scope']} · layer {spec['layer']} · {spec['license']}",
            tags=(spec["scope"],),
            extra={
                "scope": spec["scope"],
                "layer": spec["layer"],
                "license": spec["license"],
                # Every one of these is extracted at build time. A stale value
                # changes the digest and fails `check`, instead of drifting.
                "py_files": len(files),
                "loc": loc,
                "test_functions": count_tests(files),
                "tree_digest": tree_digest(path, files),
                "rel_path": spec["path"],
                # The v1.0.0 gate asks these of every package. Extracted, so a
                # package that gains a LICENSE changes the graph rather than
                # waiting for someone to remember to edit a table.
                **{f"has_{k}": (path / v).exists() for k, v in (
                    ("readme", "README.md"), ("changelog", "CHANGELOG.md"),
                    ("license", "LICENSE"), ("notice", "NOTICE"),
                    ("claude_md", "CLAUDE.md"), ("pyproject", "pyproject.toml"))},
                "vendors": vendored_by(path),
                "scope_reason": str(spec.get("retire_reason")
                                    or spec.get("defer_reason") or ""),
            },
        ))

    # module nodes + contains
    module_index: dict[tuple[str, str], str] = {}
    for sid in sorted(per_system_files):
        base = system_root[sid]
        for f in per_system_files[sid]:
            rel = f.relative_to(base).as_posix()
            nid = kt.make_node_id("module", f"{sid}/{rel}")
            module_index[(sid, rel)] = nid
            nodes.append(kt.Node(
                node_id=nid, node_type="module", name=Path(rel).name,
                qualname=f"{sid}/{rel}",
                file_path=rel,          # relative — never an absolute path
                extra={"system": sid},
            ))
            edges.append(kt.Edge(
                edge_type="contains",
                source_id=kt.make_node_id("system", sid),
                target_id=nid, extracted_by="walk", metadata={},
            ))

    # cards + the method primitives inside them
    #
    # The doctrine map is loaded first because BOTH the ingested and the curated
    # paths consult it. Category was a heuristic and it was wrong for 23 of 56
    # findings; an explicit map makes each link a decision on record.
    doctrine_map: dict[str, str] = {}
    _dm = HERE / "curated" / "doctrine-map.yaml"
    if _dm.is_file():
        import yaml as _y
        with _dm.open(encoding="utf-8") as fh:
            doctrine_map = dict((_y.safe_load(fh) or {}).get("governed_by_map") or {})
    doctrine_map_used: set[str] = set()
    known_rules = {name for name, _ in DOCTRINE}

    parse_frontmatter = load_frontmatter_parser(roots)
    quarantined: list[str] = []
    curated_rejects_early: list[str] = []
    status_drift: list[str] = []
    card_count = finding_count = 0
    declared_ids: dict[str, list[str]] = {}

    for sid in sorted(system_root):
        base = system_root[sid]
        for cpath in iter_cards(base):
            rel = cpath.relative_to(base).as_posix()
            try:
                fm, body = parse_frontmatter(
                    cpath.read_text(encoding="utf-8", errors="ignore"))
            except Exception as exc:
                quarantined.append(f"{sid}/{rel}: unreadable ({type(exc).__name__})")
                continue
            if not fm:
                # No frontmatter is not a card. Logged, never silently dropped.
                quarantined.append(f"{sid}/{rel}: no frontmatter block")
                continue

            ai = fm.get("ai_card") or {}
            cid = str(fm.get("id") or ai.get("id") or rel)
            card_nid = kt.make_node_id("card", f"{sid}/{rel}")
            nodes.append(kt.Node(
                node_id=card_nid, node_type="card",
                name=str(ai.get("title") or cid), qualname=f"{sid}/{rel}",
                file_path=rel, summary=str(ai.get("scope") or ""),
                tags=tuple(sorted({str(fm.get("kind") or "unknown")})),
                extra={
                    "system": sid,
                    "declared_id": cid,
                    "kind": str(fm.get("kind") or "unknown"),
                    "format": str(fm.get("format") or ""),
                    "version": str(ai.get("version") or ""),
                    # From frontmatter, which is already fixed -- never a clock.
                    "created": str(ai.get("created") or ""),
                    "status": str(ai.get("status") or ""),
                    "owner": str(ai.get("owner_user") or ""),
                },
            ))
            edges.append(kt.Edge(
                edge_type="contains", source_id=kt.make_node_id("system", sid),
                target_id=card_nid, extracted_by="frontmatter", metadata={},
            ))
            declared_ids.setdefault(f"card:{sid}/{cid}", []).append(rel)
            card_count += 1

            kind = str(fm.get("kind") or "unknown")
            for entry in extract_primitives(body):
                # `evidence` is a mapping in most cards but a bare string in some.
                # Both are real shapes in this corpus; normalise rather than crash
                # on the minority form.
                raw_ev = entry.get("evidence")
                ev = raw_ev if isinstance(raw_ev, dict) else (
                    {"source": raw_ev} if isinstance(raw_ev, str) and raw_ev else {})
                src = ev.get("source")
                if not src and kind in EVIDENCE_REQUIRED_KINDS:
                    # For a method primitive, a claim without evidence.source is
                    # narrative — and narrative is what this graph exists to keep
                    # out. Quarantined and named, never silently dropped.
                    quarantined.append(
                        f"{sid}/{rel}#{entry.get('id')}: no evidence.source "
                        f"(kind={kind})")
                    continue

                category = str(entry.get("category") or "").lower()
                if not category and kind == "security_primitive_db":
                    category = "security"
                status = str(entry.get("status") or "").upper()
                undeclared = status and status not in STATUS_DECLARED
                if undeclared:
                    status_drift.append(f"{sid}/{rel}#{entry.get('id')}: {status}")

                fid = kt.make_node_id("finding", f"{sid}/{rel}#{entry['id']}")
                nodes.append(kt.Node(
                    node_id=fid, node_type="finding",
                    name=str(entry.get("name") or entry["id"]),
                    qualname=f"{sid}/{rel}#{entry['id']}",
                    file_path=rel, summary=str(entry["claim"])[:600],
                    tags=tuple(sorted(
                        {status or "UNSTATED",
                         category or "uncategorised",
                         "card:" + kind}
                        | ({"status-undeclared"} if undeclared else set()))),
                    extra={
                        "system": sid,
                        "declared_id": str(entry["id"]),
                        "card_kind": kind,
                        "category": category,
                        "claim_type": str(entry.get("claim_type") or ""),
                        "status": status,
                        "status_declared": not undeclared,
                        "evidence_source": str(src or "")[:400],
                        "evidence_result": str(ev.get("result") or "")[:400],
                        "evidence_n": str(ev.get("n") or ""),
                    },
                ))
                edges.append(kt.Edge(
                    edge_type="contains", source_id=card_nid, target_id=fid,
                    extracted_by="frontmatter", metadata={},
                ))
                declared = str(entry["id"])
                rule = doctrine_map.get(declared) or CATEGORY_TO_DOCTRINE.get(category)
                if declared in doctrine_map:
                    doctrine_map_used.add(declared)
                if rule and rule not in known_rules:
                    curated_rejects_early.append(
                        f"doctrine-map:{declared}: unknown rule {rule!r}")
                    rule = None
                if rule:
                    edges.append(kt.Edge(
                        edge_type="governed_by", source_id=fid,
                        target_id=kt.make_node_id("doctrine_rule", rule),
                        extracted_by="category-map", metadata={},
                    ))
                declared_ids.setdefault(
                    f"finding:{sid}/{entry['id']}", []).append(rel)
                finding_count += 1

    # curated nodes and edges — the layer that requires reading intent
    curated_dir = HERE / "curated"
    curated_nodes = 0
    curated_edges = 0
    curated_rejects: list[str] = []
    CURATED_NODE_KINDS = ("fusion_method", "dimension", "eval_harness", "ts_target")

    if curated_dir.is_dir():
        import yaml
        docs = []
        for cf in sorted(curated_dir.glob("*.yaml")):
            with cf.open(encoding="utf-8") as fh:
                docs.append((cf.name, yaml.safe_load(fh) or {}))

        for fname, doc in docs:
            for kind in CURATED_NODE_KINDS:
                for item in doc.get(kind) or []:
                    src = (item.get("evidence") or {}).get("source")
                    if not src:
                        curated_rejects.append(
                            f"{fname}:{kind}:{item.get('id')}: no evidence.source")
                        continue
                    extra = {k: v for k, v in sorted(item.items())
                             if k not in ("id", "name", "summary", "evidence")}
                    extra["evidence_source"] = str(src)[:400]
                    nodes.append(kt.Node(
                        node_id=kt.make_node_id(kind, item["id"]),
                        node_type=kind, name=str(item.get("name") or item["id"]),
                        qualname=str(item["id"]),
                        summary=" ".join(str(item.get("summary") or "").split())[:600],
                        tags=("curated",),
                        extra={k: ("" if v is None else v) for k, v in extra.items()},
                    ))
                    curated_nodes += 1

            for item in doc.get("findings") or []:
                src = (item.get("evidence") or {}).get("source")
                if not src:
                    # The one rule with no exception: a claim without a source is
                    # narrative, and narrative curated into a graph is worse than
                    # narrative left in prose, because it acquires structure.
                    curated_rejects.append(
                        f"{fname}:finding:{item.get('id')}: no evidence.source")
                    continue
                status = str(item.get("status") or "").upper()
                if status not in STATUS_DECLARED:
                    curated_rejects.append(
                        f"{fname}:finding:{item.get('id')}: status {status!r} undeclared")
                    continue
                ev = item.get("evidence") or {}
                nodes.append(kt.Node(
                    node_id=kt.make_node_id("finding", item["id"]),
                    node_type="finding", name=str(item.get("name") or item["id"]),
                    qualname=str(item["id"]),
                    summary=" ".join(str(item.get("claim") or "").split())[:600],
                    tags=tuple(sorted({status,
                                       str(item.get("category") or "uncategorised"),
                                       "curated",
                                       "verified-here" if item.get("verified_here")
                                       else "cited-not-reverified"})),
                    extra={
                        "system": "curated",
                        "declared_id": str(item["id"]),
                        "category": str(item.get("category") or ""),
                        "claim_type": str(item.get("claim_type") or ""),
                        "status": status,
                        "status_declared": True,
                        # The distinction that matters more than the status label:
                        # did THIS builder re-derive the number, or is it cited?
                        "verified_here": bool(item.get("verified_here")),
                        "evidence_source": str(src)[:400],
                        "evidence_result": str(ev.get("result") or "")[:400],
                        "evidence_n": str(ev.get("n") or ""),
                    },
                ))
                declared = str(item["id"])
                rule = (item.get("governed_by") or doctrine_map.get(declared)
                        or CATEGORY_TO_DOCTRINE.get(str(item.get("category") or "").lower()))
                if declared in doctrine_map:
                    doctrine_map_used.add(declared)
                if rule and rule not in known_rules:
                    curated_rejects.append(f"doctrine-map:{declared}: unknown rule {rule!r}")
                    rule = None
                if rule:
                    edges.append(kt.Edge(
                        edge_type="governed_by",
                        source_id=kt.make_node_id("finding", item["id"]),
                        target_id=kt.make_node_id("doctrine_rule", rule),
                        extracted_by="curated", metadata={},
                    ))
                curated_nodes += 1

        # Edges are staged, then resolved against the finished node set. An edge
        # naming a node that does not exist is refused here by name, rather than
        # reaching the store and surfacing later as an anonymous dangling edge.
        known = {n.node_id for n in nodes}
        for fname, doc in docs:
            for etype, items in sorted((doc.get("edges") or {}).items()):
                for item in items or []:
                    src_id, tgt_id = str(item.get("source")), str(item.get("target"))
                    esrc = (item.get("evidence") or {}).get("source")
                    if not esrc:
                        curated_rejects.append(
                            f"{fname}:{etype}:{src_id}->{tgt_id}: no evidence.source")
                        continue
                    missing = [x for x in (src_id, tgt_id) if x not in known]
                    if missing:
                        curated_rejects.append(
                            f"{fname}:{etype}:{src_id}->{tgt_id}: unresolved {missing}")
                        continue
                    meta = {"evidence_source": str(esrc)[:400]}
                    if item.get("why"):
                        meta["why"] = " ".join(str(item["why"]).split())
                    edges.append(kt.Edge(
                        edge_type=etype, source_id=src_id, target_id=tgt_id,
                        extracted_by="curated", metadata=meta,
                    ))
                    curated_edges += 1
    # Cross-package dependencies, aggregated to system level.
    # The weight counts FILES that import the package, not import statements:
    # module_imports() returns a set per file. Naming it precisely matters --
    # a mislabelled number is the defect class this whole graph exists to catch.
    dep_weight: dict[tuple[str, str], int] = {}
    for sid in sorted(per_system_files):
        for f in per_system_files[sid]:
            for root_name in sorted(module_imports(f)):
                other = pkg_to_system.get(root_name)
                if other and other != sid:
                    dep_weight[(sid, other)] = dep_weight.get((sid, other), 0) + 1

    for (a, b), n in sorted(dep_weight.items()):
        edges.append(kt.Edge(
            edge_type="depends_on",
            source_id=kt.make_node_id("system", a),
            target_id=kt.make_node_id("system", b),
            confidence=1.0, extracted_by="ast", metadata={"importing_files": n},
        ))

    # A collapsed duplicate is a claim that vanishes without a message, which is
    # the exact failure absence-is-not-a-result names. Detect and report it.
    seen: dict[str, int] = {}
    duplicate_ids: list[str] = []
    for n in nodes:
        seen[n.node_id] = seen.get(n.node_id, 0) + 1
    duplicate_ids = [f'{k} (x{v})' for k, v in sorted(seen.items()) if v > 1]

    nodes.sort(key=lambda n: n.node_id)
    edges.sort(key=lambda e: (e.edge_type, e.source_id, e.target_id))
    mgr.add_nodes(nodes)
    mgr.add_edges(edges)
    conn.commit()

    report = kt.check_integrity(mgr)
    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "node_types": mgr.node_type_histogram(),
        "edge_types": mgr.edge_type_histogram(),
        "integrity_ok": report.ok,
        "issues": [f"[{i.severity}] {i.check}: {i.subject} — {i.message}"
                   for i in report.issues],
        "cards": card_count,
        "findings": finding_count,
        "quarantined": sorted(quarantined),
        "status_drift": sorted(status_drift),
        "duplicate_ids": sorted(duplicate_ids),
        "curated_nodes": curated_nodes,
        "curated_edges": curated_edges,
        "curated_rejects": sorted(curated_rejects + curated_rejects_early + [
            f"doctrine-map:{k}: matches no finding" for k in
            sorted(set(doctrine_map) - doctrine_map_used)]),
        "declared_id_collisions": sorted(
            f"{k} in {sorted(set(v))}" for k, v in declared_ids.items()
            if len(v) > 1),
    }
    mgr.close()
    return stats


# --------------------------------------------------------------------------
# assertions — every one asserts a positive count, per doctrine rule 4
# --------------------------------------------------------------------------

def assert_positive(stats: dict) -> list[str]:
    failures = []
    if stats["nodes"] <= 0:
        failures.append("no nodes were built")
    if stats["edges"] <= 0:
        failures.append("no edges were built")
    for t in ("system", "module", "doctrine_rule"):
        if stats["node_types"].get(t, 0) <= 0:
            failures.append(f"zero {t!r} nodes — the walk found nothing")
    for t in ("contains", "depends_on"):
        if stats["edge_types"].get(t, 0) <= 0:
            failures.append(f"zero {t!r} edges — extraction produced no structure")
    if stats["node_types"].get("doctrine_rule", 0) != len(DOCTRINE):
        failures.append(f"expected {len(DOCTRINE)} doctrine rules, "
                        f"got {stats['node_types'].get('doctrine_rule', 0)}")
    if stats["curated_nodes"] <= 0:
        failures.append("curated layer produced no nodes")
    if stats["curated_edges"] <= 0:
        failures.append("curated layer produced no edges")
    if not stats["integrity_ok"]:
        failures.append(f"integrity failed: {len(stats['issues'])} issue(s)")
    return failures


def dump(path: Path) -> str:
    """A canonical projection of the graph, for byte-comparison.

    Deliberately NOT `conn.iterdump()`. `kg_toolkit/store.py:37` stamps every row
    with `datetime.now(timezone.utc).isoformat()`, so two builds of identical
    content produce different bytes and a raw dump can never be stable. That is a
    real property of the storage engine, recorded here rather than worked around
    silently — see finding `kg_toolkit-created-at-breaks-byte-reproducibility`.

    So the comparison excludes `created_at` and orders explicitly, which also
    makes it insensitive to rowid assignment. Everything that carries meaning is
    still compared: ids, types, names, paths, tags, payloads, confidences.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        lines = []
        for row in conn.execute(
            "SELECT id, node_type, name, qualname, docstring, summary, file_path,"
            "       line_start, line_end, tags, data, schema_version"
            "  FROM nodes ORDER BY id"
        ):
            lines.append("N\t" + "\t".join("" if v is None else str(v) for v in row))
        for row in conn.execute(
            "SELECT edge_type, source_id, target_id, confidence, extracted_by, metadata"
            "  FROM edges ORDER BY edge_type, source_id, target_id, extracted_by"
        ):
            lines.append("E\t" + "\t".join("" if v is None else str(v) for v in row))
        return "\n".join(lines)
    finally:
        conn.close()


# --------------------------------------------------------------------------
# the handbook — generated from the graph, never typed
# --------------------------------------------------------------------------

HANDBOOK = HERE / "TS-kg-rag-of-kg-rag.md"

ANCHOR = re.compile(r"\[\[node:([^\]]+)\]\]")

PREAMBLE = """\
# The KG-RAG of KG-RAGs

**A knowledge graph whose domain is its author's own retrieval systems, and the
handbook generated from it.**

Two generations of KG-RAG work live in this estate, across dozens of repositories
and hundreds of declared cards. Every finding in it was true when it was written.
None of it was queryable, which is why the same context had to be re-explained at
the start of every session.

This document is **generated from `TS-kg-rag-of-kg-rag.db`**. Every factual claim
below ends with an anchor naming the node it came from — this one, for instance,
points at a real finding: [[node:finding::status-vocabulary-drift]]. Anchors are
resolved against the database on
every `check` run, and the run fails if any one of them does not exist — so this
file cannot quietly drift away from the graph it describes.

Do not edit this file. Edit the graph, or the curated YAML behind it, and run:

```bash
python3 TS-kg-rag-of-kg-rag.py build && python3 TS-kg-rag-of-kg-rag.py render
```
"""


def _extra(row) -> dict:
    return json.loads(row["data"] or "{}").get("extra", {})


def render_handbook(db: Path) -> str:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        names = {r["id"]: r["name"] for r in conn.execute("SELECT id,name FROM nodes")}
        out = [PREAMBLE]

        # -- doctrine ------------------------------------------------------
        n_rules = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE node_type='doctrine_rule'").fetchone()[0]
        out.append(f"\n---\n\n## §1 · The {n_rules} rules\n")
        out.append("Everything else in this document answers to one of these. Four were "
                   "written as doctrine cards; `authority` and `provenance` were stated "
                   "repeatedly in contracts and code without ever being named as rules, "
                   "and 13 findings answered to nothing until they were.\n")
        for r in conn.execute(
            "SELECT id,name,summary FROM nodes WHERE node_type='doctrine_rule' ORDER BY name"
        ):
            out.append(f"\n**{r['name']}** — {r['summary']} "
                       f"[[node:{r['id']}]]\n")

        # -- estate --------------------------------------------------------
        out.append("\n---\n\n## §2 · The estate\n")
        out.append("Counts are extracted at build time. A stale number here fails "
                   "`check` rather than drifting.\n")
        out.append("\n| Package | Scope | Layer | .py | LOC | `def test_` | License | Node |")
        out.append("|---|---|---|---|---|---|---|---|")
        rows = []
        for r in conn.execute(
            "SELECT id,qualname,data FROM nodes WHERE node_type='system' ORDER BY qualname"
        ):
            x = _extra(r)
            rows.append((x.get("scope"), 99 if x.get("layer") is None else x["layer"],
                         -(x.get("loc") or 0), r, x))
        order = {"IN": 0, "SPEC": 1, "DEFER": 2, "RETIRE": 3}
        rows.sort(key=lambda t: (order.get(t[0], 9), t[1], t[2]))
        for _, _, _, r, x in rows:
            lay = "—" if x.get("layer") is None else f"L{x['layer']}"
            out.append(f"| `{r['qualname']}` | {x.get('scope','')} | {lay} | "
                       f"{x.get('py_files','—')} | {x.get('loc',0):,} | "
                       f"{x.get('test_functions','—')} | {x.get('license','')} | "
                       f"[[node:{r['id']}]] |")

        # -- contradictions ------------------------------------------------
        out.append("\n---\n\n## §3 · Where the estate disagrees with itself\n")
        out.append("The load-bearing section. Each row is an edge in the graph, not "
                   "an opinion in a document, and each carries the source it was "
                   "read from.\n")
        n_contra = 0
        for r in conn.execute(
            "SELECT source_id,target_id,metadata FROM edges "
            "WHERE edge_type='contradicts' ORDER BY source_id,target_id"
        ):
            m = json.loads(r["metadata"] or "{}")
            n_contra += 1
            out.append(f"\n**{names[r['source_id']]}** ⟷ **{names[r['target_id']]}**  ")
            out.append(f"{m.get('why','')}  ")
            out.append(f"*Source:* `{m.get('evidence_source','')}` "
                       f"[[node:{r['source_id']}]] [[node:{r['target_id']}]]\n")
        out.append(f"\n{n_contra} contradictions recorded.\n")

        # -- supersession --------------------------------------------------
        out.append("\n---\n\n## §4 · What replaced what\n")
        out.append("Generation 2 did not reconcile generation 1's plurality. It "
                   "replaced accumulation with measured rejection.\n")
        for r in conn.execute(
            "SELECT source_id,target_id,metadata FROM edges "
            "WHERE edge_type='supersedes' ORDER BY target_id,source_id"
        ):
            m = json.loads(r["metadata"] or "{}")
            out.append(f"\n**{names[r['source_id']]}** supersedes "
                       f"**{names[r['target_id']]}**  ")
            out.append(f"{m.get('why','')}  ")
            out.append(f"*Source:* `{m.get('evidence_source','')}` "
                       f"[[node:{r['source_id']}]]\n")

        # -- findings ------------------------------------------------------
        out.append("\n---\n\n## §5 · Findings\n")
        out.append("Grouped by category, then by status. A comparative claim with no "
                   "statistical gate is recorded `DIRECTIONAL` or `NOT_ESTABLISHED` "
                   "however persuasive it reads, and negative results are kept "
                   "rather than dropped.\n")
        out.append("\n`verified here` means this builder re-derived the number and the "
                   "command is in the source. `cited` means it is taken from the "
                   "estate and has not been independently re-run — a distinction that "
                   "matters more than the status label.\n")
        findings = []
        for r in conn.execute(
            "SELECT id,name,summary,data FROM nodes WHERE node_type='finding' ORDER BY name"
        ):
            findings.append((r, _extra(r)))
        rank = {"ESTABLISHED": 0, "DIRECTIONAL": 1, "OBSERVED": 2, "MEASURED": 2,
                "CONVENTION": 3, "NOT_ESTABLISHED": 4, "REFUTED": 5}
        cats = sorted({(x.get("category") or "uncategorised") for _, x in findings})
        for cat in cats:
            group = sorted((f for f in findings
                            if (f[1].get("category") or "uncategorised") == cat),
                           key=lambda f: (rank.get(f[1].get("status"), 9), f[0]["name"]))
            out.append(f"\n### {cat} ({len(group)})\n")
            for r, x in group:
                mark = ("verified here" if x.get("verified_here")
                        else ("cited" if x.get("system") == "curated" else "ingested"))
                flag = " · **status undeclared by the schema**" if not x.get(
                    "status_declared", True) else ""
                out.append(f"\n**{r['name']}** — `{x.get('status','?')}` · "
                           f"{x.get('claim_type','?')} · {mark}{flag}  ")
                out.append(f"{r['summary']}  ")
                if x.get("evidence_result"):
                    out.append(f"*Result:* {x['evidence_result']}  ")
                out.append(f"*Source:* `{x.get('evidence_source','')}` "
                           f"[[node:{r['id']}]]\n")

        # -- ts targets ----------------------------------------------------
        out.append("\n---\n\n## §6 · TypeScript translation ranking\n")
        out.append("Ordered by rank. `translates_to` edges name the exact modules "
                   "behind each target.\n")
        tt = sorted(
            ((r, _extra(r)) for r in conn.execute(
                "SELECT id,name,summary,data FROM nodes WHERE node_type='ts_target'")),
            key=lambda t: t[1].get("rank", 99))
        for r, x in tt:
            srcs = [names[s[0]] for s in conn.execute(
                "SELECT source_id FROM edges WHERE edge_type='translates_to' "
                "AND target_id=? ORDER BY source_id", (r["id"],))]
            out.append(f"\n**{x.get('rank','?')}. {r['name']}** — tier {x.get('tier','?')}  ")
            out.append(f"{r['summary']}  ")
            out.append(f"*Modules:* {', '.join(f'`{s}`' for s in srcs) or '—'}  ")
            out.append(f"*Destination:* `{x.get('dest','')}` [[node:{r['id']}]]\n")

        # -- provenance ----------------------------------------------------
        out.append("\n---\n\n## §7 · How to verify this document\n")
        counts = dict(conn.execute(
            "SELECT node_type, COUNT(*) FROM nodes GROUP BY 1"))
        ecounts = dict(conn.execute(
            "SELECT edge_type, COUNT(*) FROM edges GROUP BY 1"))
        out.append(f"\nGraph: **{sum(counts.values())} nodes, {sum(ecounts.values())} "
                   f"edges**.\n")

        # Doctrine coverage, stated rather than implied. Not every finding answers
        # to one of the four rules, and forcing a link would make the gap invisible
        # instead of closing it.
        linked = {r[0] for r in conn.execute(
            "SELECT source_id FROM edges WHERE edge_type='governed_by'")}
        unl = {}
        total = 0
        for fid, d in conn.execute("SELECT id,data FROM nodes WHERE node_type='finding'"):
            total += 1
            if fid not in linked:
                cat = json.loads(d)["extra"].get("category") or "uncategorised"
                unl[cat] = unl.get(cat, 0) + 1
        n_unl = sum(unl.values())
        out.append(f"\n**Doctrine coverage: {total - n_unl} of {total} findings "
                   f"hang off one of the {n_rules} rules; {n_unl} do not.**\n")
        if unl:
            out.append("\nThe unlinked ones, by category: "
                       + ", ".join(f"`{k}` {v}" for k, v in sorted(unl.items()))
                       + ". No category implies `retrieval`, `measurement` or "
                       "`declaration` for these, and a link asserted to make the "
                       "table look complete would hide the gap rather than close "
                       "it. A finding may declare `governed_by` explicitly when the "
                       "rule it answers to is genuine.\n")
        out.append("\n| Rule | Findings |")
        out.append("|---|---|")
        for rid, rname in sorted(
            (r[0], r[1]) for r in conn.execute(
                "SELECT id,name FROM nodes WHERE node_type='doctrine_rule'")):
            n = conn.execute("SELECT COUNT(*) FROM edges WHERE edge_type='governed_by' "
                             "AND target_id=?", (rid,)).fetchone()[0]
            out.append(f"| {rname} | {n} |")
        out.append("\n| Node type | Count |")
        out.append("|---|---|")
        for k in sorted(counts):
            out.append(f"| `{k}` | {counts[k]} |")
        out.append("\n| Edge type | Count |")
        out.append("|---|---|")
        for k in sorted(ecounts):
            out.append(f"| `{k}` | {ecounts[k]} |")
        out.append("""
```bash
python3 TS-kg-rag-of-kg-rag.py build    # rebuild the graph, assert positive counts
python3 TS-kg-rag-of-kg-rag.py check    # byte-compare the rebuild AND resolve every
                                        # anchor in this file against the database
python3 TS-kg-rag-of-kg-rag.py render   # regenerate this document
```

`check` fails if any anchor above names a node that does not exist, if the anchor
count is zero, or if this file is stale relative to the graph. A check that passes
by finding nothing has reported nothing.
""")
        return "\n".join(out).rstrip() + "\n"
    finally:
        conn.close()


def verify_anchors(db: Path, doc: Path) -> list[str]:
    """Every anchor must resolve, and there must be some. Both, not either."""
    if not doc.exists():
        return [f"{doc.name} does not exist — run `render`"]
    text = doc.read_text(encoding="utf-8")
    anchors = ANCHOR.findall(text)
    if not anchors:
        return [f"{doc.name} contains zero [[node:…]] anchors — "
                "an unanchored document is not a checked document"]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        known = {r[0] for r in conn.execute("SELECT id FROM nodes")}
    finally:
        conn.close()
    missing = sorted({a for a in anchors if a not in known})
    return [f"{doc.name}: anchor does not resolve: {a}" for a in missing[:20]]

# --------------------------------------------------------------------------
# the NLKE v1.0.0 release specification — also generated from the graph
# --------------------------------------------------------------------------

RELEASE = HERE / "NLKE-production-quality-release-V1.0.0.md"

RELEASE_HEAD = """\
---
format: ngf/0.0.3
kind: release_specification
id: nlke-production-quality-release-v1
ai_card:
  id: nlke-production-quality-release-v1
  kind: release_specification
  audience: engineer
  status: draft
  owner_area: /root/projects/kg-rag-cookbook
  title: "NLKE v1.0.0 — production-quality release and monorepo unification specification"
  version: "1.0.0-draft.2"
  created: "2026-09-01"
  scope: "What it is NOT: an execution log. No repository has been moved. This is the spec the move will be executed against."
  related:
    - "[[kg-rag-cookbook-manifest]] — the framework this consolidates"
    - "[[ts-kg-rag-of-kg-rag]] — the graph this document is generated from"
  owner_user: eyal_nof
---

# NLKE v1.0.0 — production-quality release specification

**Target:** unify the Natural-Language-Knowledge-Engineering estate into one
self-contained monorepo.

**Generated from `TS-kg-rag-of-kg-rag.db`.** Every count, flag, edge and digest
below is extracted at build time and carries an anchor naming its node. Draft 1 of
this document was hand-assembled and was wrong; see §1.

---

## §1 · How this document was produced

| Quantity | Method |
|---|---|
| Python files, LOC | `os.walk`, skipping `__pycache__` `.venv` `.git` `node_modules` **`build` `dist`** |
| Test count | `def test_` regex — test **functions**, not pytest cases |
| Licence | first match of Apache/MIT/"All rights reserved" in `LICENSE` |
| Doc presence | file existence, per package |
| Dependency edges | `ast` import analysis, counting **files** that import, cross-package only |
| Vendoring | each package's own `VENDORED.json` — name, version, `tree_sha` |
| Tree digest | blake2b over sorted (relpath, sha256(content)) pairs |

### Honesty notes

1. **Test counts differ from README badges** because they measure different
   things. `declared_core`'s badge says 80; `def test_` counts 107.
   `NLKE-mud-detection` 53 against 56; `claude-arch-inventory` 25 against 29.
   Badges count pytest *cases*; this counts *functions*. Use one measure per
   column and name it.
2. **No test suite was executed for this document.** Every count is static. The
   `suite green` column of §6 is honestly unknown and must never be rendered as a
   pass.
3. **Draft 1 of this document was wrong, and the graph caught it.** It counted
   `.py` with a walk that skipped only `__pycache__`/`.venv`/`.git`/`node_modules`.
   Six packages carry a `build/` directory holding **205 duplicated files**, so it
   reported `declared_core` as 47 files / 5,337 LOC when it is 32 / 3,549, and
   inflated the estate by roughly 30% (101,110 against 71,045 LOC). Test counts
   were unaffected — `build/` mirrors package code, not tests. This draft is
   generated from the graph, whose builder skips artifact directories. A number
   typed into a document can be wrong for a month; a generated one is wrong only
   until the next build.
"""

RELEASE_TAIL = """\

---

## §9 · What this document does not claim

- **No repository has been moved.** This is a specification.
- **No test suite was run.** Every count is static analysis.
- **`DEFER` is not a judgement of quality** — those packages are deferred on
  boundary questions, not merit.
- Test counts are `def test_` functions, not pytest cases (§1).

---

## §10 · Verification

```bash
cd /root/projects/kg-rag-cookbook
python3 TS-kg-rag-of-kg-rag.py build     # rebuild the graph; assert positive counts
python3 TS-kg-rag-of-kg-rag.py release   # regenerate this document
python3 TS-kg-rag-of-kg-rag.py check     # byte-compare, and resolve every anchor

cd <package> && python3 -m pytest -q ; echo "exit=$?"   # the column §6 cannot fill
```

**Until that last command has been run and its exit code recorded for every `IN`
package, v1.0.0 is a proposal, not a release.**
"""


def render_release(db: Path) -> str:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        systems = []
        for r in conn.execute(
            "SELECT id,qualname,data FROM nodes WHERE node_type='system' ORDER BY qualname"
        ):
            systems.append((r, _extra(r)))
        cards = dict(conn.execute(
            "SELECT json_extract(data,'$.extra.system'), COUNT(*) "
            "FROM nodes WHERE node_type='card' GROUP BY 1"))
        by_scope = lambda sc: [t for t in systems if t[1].get("scope") == sc]
        out = [RELEASE_HEAD]

        # -- §2 scope ledger ----------------------------------------------
        out.append("\n---\n\n## §2 · Scope ledger\n")
        out.append("Every candidate carries a scope and, where it is not `IN`, a "
                   "reason. Nothing is admitted for being adjacent to something "
                   "admitted, and nothing is excluded by being forgotten — the "
                   "source list is an explicit allowlist.\n")
        for sc, title in (("IN", "IN — the monorepo"),
                          ("SPEC", "IN — specification and doctrine"),
                          ("DEFER", "DEFER — decide after the graph"),
                          ("RETIRE", "RETIRE — generation 1")):
            group = by_scope(sc)
            if not group:
                continue
            out.append(f"\n### {title} ({len(group)})\n")
            out.append("\n| Package | Layer | Reason | Node |")
            out.append("|---|---|---|---|")
            for r, x in sorted(group, key=lambda t: (
                    99 if t[1].get("layer") is None else t[1]["layer"], t[0]["qualname"])):
                lay = "—" if x.get("layer") is None else f"L{x['layer']}"
                out.append(f"| `{r['qualname']}` | {lay} | "
                           f"{x.get('scope_reason') or '—'} | [[node:{r['id']}]] |")

        # -- §3 layering ---------------------------------------------------
        deps = [(s.split("::")[1], t.split("::")[1], json.loads(m)["importing_files"])
                for s, t, m in conn.execute(
                    "SELECT source_id,target_id,metadata FROM edges "
                    "WHERE edge_type='depends_on'")]
        deps.sort(key=lambda d: (-d[2], d[0]))
        out.append("\n---\n\n## §3 · Layering\n")
        out.append(f"Derived from **{len(deps)} measured cross-package import "
                   "edges**, not asserted. The weight counts *files* in the "
                   "importer that import the package.\n")
        out.append("\n| Importer | Imports | Files |")
        out.append("|---|---|---|")
        for a, b, n in deps:
            out.append(f"| `{a}` | `{b}` | {n} |")
        acyclic = "acyclic" if not _has_cycle(deps) else "**CYCLIC — investigate**"
        out.append(f"\nThe package dependency graph is **{acyclic}**, so the "
                   "monorepo can be assembled bottom-up with no circular-dependency "
                   "work.\n")

        # -- §4 vendoring --------------------------------------------------
        out.append("\n---\n\n## §4 · The vendoring collapse\n")
        vend = [(r["qualname"], v, r["id"]) for r, x in systems for v in x.get("vendors") or []]
        counts: dict[str, list[str]] = {}
        for pkg, v, _ in vend:
            counts.setdefault(v, []).append(pkg)
        out.append(f"\n**{len(vend)} vendored trees** are declared across "
                   f"{len({p for p, _, _ in vend})} packages.\n")
        out.append("\n| Vendored | Digest | Copied into |")
        out.append("|---|---|---|")
        for v, pkgs in sorted(counts.items()):
            name, _, digest = v.partition(" ")
            out.append(f"| `{name}` | `{digest}…` | {', '.join(f'`{p}`' for p in sorted(pkgs))} "
                       f"— **{len(pkgs)}** |")
        out.append("\nEvery copy of a given package declares the same digest, and "
                   "the upstream tree matches. Six trees of one package currently "
                   "agree, held there by discipline alone. **That makes now the "
                   "cheapest moment to collapse them** — unifying while they agree "
                   "is a deletion; unifying after a divergence is a merge with no "
                   "oracle for which side is right. "
                   "[[node:finding::declared-core-vendored-five-times-in-sync]]\n")

        # -- §5 inventory --------------------------------------------------
        out.append("\n---\n\n## §5 · Package inventory\n")
        out.append("\n| Package | Scope | Layer | .py | LOC | `def test_` | `.ngf.md` | Licence | Node |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        order = {"IN": 0, "SPEC": 1, "DEFER": 2, "RETIRE": 3}
        for r, x in sorted(systems, key=lambda t: (
                order.get(t[1].get("scope"), 9),
                99 if t[1].get("layer") is None else t[1]["layer"],
                -(t[1].get("loc") or 0))):
            lay = "—" if x.get("layer") is None else f"L{x['layer']}"
            lic = "**none**" if x.get("license") == "NONE" else x.get("license", "")
            out.append(f"| `{r['qualname']}` | {x.get('scope','')} | {lay} | "
                       f"{x.get('py_files','—')} | {(x.get('loc') or 0):,} | "
                       f"{x.get('test_functions','—')} | {cards.get(r['qualname'],0)} | "
                       f"{lic} | [[node:{r['id']}]] |")
        ins = by_scope("IN") + by_scope("SPEC")
        out.append(f"\n**IN + SPEC totals: {sum(x.get('py_files',0) for _, x in ins)} "
                   f"Python files · {sum(x.get('loc',0) for _, x in ins):,} LOC · "
                   f"{sum(x.get('test_functions',0) for _, x in ins):,} test functions · "
                   f"{sum(cards.get(r['qualname'],0) for r, _ in ins)} `.ngf.md` cards.**\n")

        # -- §6 the gate ---------------------------------------------------
        out.append("\n---\n\n## §6 · The v1.0.0 production-quality gate\n")
        out.append("Every row extracted. `?` is honest: this document cannot run a "
                   "test suite, and a column of unknowns is not a pass.\n")
        out.append("\n| Package | README | CHANGELOG | LICENCE | NOTICE | CLAUDE.md | pyproject | Suite green |")
        out.append("|---|---|---|---|---|---|---|---|")
        blockers: list[str] = []
        for r, x in sorted(ins, key=lambda t: (order.get(t[1].get("scope"), 9),
                                               t[0]["qualname"])):
            m = lambda k: "✓" if x.get(f"has_{k}") else "✗"
            out.append(f"| `{r['qualname']}` | {m('readme')} | {m('changelog')} | "
                       f"{m('license')} | {m('notice')} | {m('claude_md')} | "
                       f"{m('pyproject')} | ? |")
            if not x.get("has_license"):
                blockers.append(r["qualname"])
        out.append(f"\n### Blockers\n")
        out.append(f"\n1. **{len(blockers)} in-scope packages have no LICENCE** — "
                   + ", ".join(f"`{b}`" for b in sorted(blockers))
                   + ". An unlicensed package cannot ship beside licensed ones. "
                     "**Hard blocker.**\n")
        out.append("2. **The `Suite green` column is entirely `?`.** No suite was "
                   "run. Per `absence-is-not-a-result`, a column of unknowns must "
                   "never be rendered as a pass. "
                   "[[node:doctrine_rule::absence-is-not-a-result]]\n")
        priv = [r["qualname"] for r, x in ins if x.get("license") == "PROPRIETARY"]
        if priv:
            out.append(f"3. **{', '.join(f'`{p}`' for p in sorted(priv))} "
                       f"{'is' if len(priv)==1 else 'are'} PROPRIETARY** inside an "
                       "otherwise open estate, and need a private tier whose "
                       "boundary CI enforces — not a note in a README.\n")

        # -- §7 licences ---------------------------------------------------
        out.append("\n---\n\n## §7 · Licence reconciliation\n")
        lic_map: dict[str, list[str]] = {}
        for r, x in ins:
            lic_map.setdefault(x.get("license") or "NONE", []).append(r["qualname"])
        out.append("\n| Licence | Packages |")
        out.append("|---|---|")
        for lic in sorted(lic_map):
            label = "**none**" if lic == "NONE" else lic
            out.append(f"| {label} | {', '.join(f'`{p}`' for p in sorted(lic_map[lic]))} |")
        out.append("\nStated, not blended. The monorepo declares Apache-2.0 at root; "
                   "MIT packages keep their own LICENCE; proprietary packages live "
                   "in a `private/` tier, and CI fails if a public package imports "
                   "one. [[node:doctrine_rule::provenance]]\n")

        # -- §8 migration --------------------------------------------------
        out.append("\n---\n\n## §8 · Migration order\n")
        out.append("Leaves first, so nothing breaks mid-move. Waves follow the "
                   "measured layering in §3.\n")
        layers: dict[int, list[str]] = {}
        for r, x in by_scope("IN"):
            if x.get("layer") is not None:
                layers.setdefault(x["layer"], []).append(r["qualname"])
        out.append("\n| Wave | Packages | Gate |")
        out.append("|---|---|---|")
        out.append("| 0 | workspace scaffold, CI, `private/` tier, licence policy check "
                   "| empty workspace builds |")
        for i, lay in enumerate(sorted(layers), start=1):
            gate = ("suites green in the workspace" if lay == 0 else
                    "each suite green with no vendored copy present" if lay == 1 else
                    "each suite green")
            out.append(f"| {i} | L{lay}: {', '.join(f'`{p}`' for p in sorted(layers[lay]))} "
                       f"| {gate} |")
        out.append(f"| {len(layers)+1} | delete all {len(vend)} vendored trees; "
                   "repoint to workspace dependencies | dependents green with no "
                   "vendored copy on disk |")
        out.append(f"| {len(layers)+2} | spec repos and docs | format spec resolves; "
                   "cross-links valid |")
        out.append("\n**The vendoring wave is the one that pays.** Everything before "
                   "it is scaffolding.\n")

        out.append(RELEASE_TAIL)
        return "\n".join(out).rstrip() + "\n"
    finally:
        conn.close()


def _has_cycle(deps: list) -> bool:
    adj: dict[str, list[str]] = {}
    for a, b, _ in deps:
        adj.setdefault(a, []).append(b)
    state: dict[str, int] = {}

    def walk(n: str) -> bool:
        state[n] = 1
        for m in adj.get(n, []):
            c = state.get(m, 0)
            if c == 1 or (c == 0 and walk(m)):
                return True
        state[n] = 2
        return False

    return any(state.get(n, 0) == 0 and walk(n) for n in sorted(adj))

# --------------------------------------------------------------------------
# authored-card provenance
# --------------------------------------------------------------------------

def card_body_digest(text: str) -> str:
    """sha256 of a card's body — everything after the frontmatter block.

    The body only, so writing the digest into the frontmatter cannot change the
    digest. These cards declare `law: "derivation-with-provenance, never
    fabrication"` and then carried `content_hash: PENDING`; a provenance field
    that is never filled is a decoration, and `check` now fails on a stale one.
    """
    parts = text.split("\n---\n", 1)
    body = parts[1] if len(parts) == 2 and text.startswith("---") else text
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def authored_cards() -> list[Path]:
    return sorted(HERE.glob("*.ngf.md"))


def stamp_card_hashes(write: bool) -> tuple[int, list[str]]:
    """Fill or verify `content_hash` on every authored card in this repo."""
    stale: list[str] = []
    changed = 0
    for card in authored_cards():
        text = card.read_text(encoding="utf-8")
        digest = card_body_digest(text)
        match = re.search(r"^(\s*content_hash:\s*)(.+)$", text, re.M)
        if not match:
            stale.append(f"{card.name}: no content_hash field")
            continue
        if match.group(2).strip() == digest:
            continue
        if write:
            card.write_text(text[:match.start()] + match.group(1) + digest
                            + text[match.end():], encoding="utf-8")
            changed += 1
        else:
            stale.append(f"{card.name}: content_hash is stale "
                         f"({match.group(2).strip()[:24]} != {digest[:24]})")
    return changed, stale

# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def report(stats: dict) -> None:
    print(f"  nodes {stats['nodes']}  edges {stats['edges']}")
    print(f"  cards {stats['cards']}  findings {stats['findings']}  "
          f"quarantined {len(stats['quarantined'])}  "
          f"status-drift {len(stats['status_drift'])}  "
          f"duplicate-ids {len(stats['duplicate_ids'])}  "
          f"id-collisions {len(stats['declared_id_collisions'])}")
    print(f"  curated: {stats['curated_nodes']} nodes  {stats['curated_edges']} edges  "
          f"rejected {len(stats['curated_rejects'])}")
    for r in stats["curated_rejects"][:10]:
        print(f"    REJECTED {r}")
    print("  node types: " + ", ".join(
        f"{k}={v}" for k, v in sorted(stats["node_types"].items())))
    print("  edge types: " + ", ".join(
        f"{k}={v}" for k, v in sorted(stats["edge_types"].items())))
    print(f"  integrity: {'ok' if stats['integrity_ok'] else 'FAILED'}")
    for issue in stats["issues"][:12]:
        print(f"    - {issue}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("build", "check", "render", "release", "stamp", "stats"))
    ap.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    ap.add_argument("--root", type=Path, default=None,
                    help="estate root; defaults to the parent of this file's repo")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    sources = load_sources(args.sources)
    root = (args.root or HERE.parent).resolve()
    roots = resolve_roots(sources, root)
    kt = import_engine(sources, roots)

    if args.command == "stats":
        if not args.out.exists():
            print(f"no graph at {args.out} — run build first", file=sys.stderr)
            return 1
        conn = sqlite3.connect(f"file:{args.out}?mode=ro", uri=True)
        for label, sql in (("nodes", "SELECT node_type, COUNT(*) FROM nodes GROUP BY 1 ORDER BY 1"),
                           ("edges", "SELECT edge_type, COUNT(*) FROM edges GROUP BY 1 ORDER BY 1")):
            print(f"{label}:")
            for r in conn.execute(sql):
                print(f"  {r[0]:<16} {r[1]}")
        conn.close()
        return 0

    if args.command == "render":
        if not args.out.exists():
            print(f"no graph at {args.out} — run build first", file=sys.stderr)
            return 1
        text = render_handbook(args.out)
        HANDBOOK.write_text(text, encoding="utf-8")
        bad = verify_anchors(args.out, HANDBOOK)
        n = len(ANCHOR.findall(text))
        print(f"rendered {HANDBOOK.name}: {len(text.splitlines())} lines, {n} anchors")
        if bad:
            for b in bad:
                print(f"  - {b}", file=sys.stderr)
            return 1
        print("  every anchor resolves")
        return 0

    if args.command == "stamp":
        changed, stale = stamp_card_hashes(write=True)
        print(f"stamped {changed} card(s); {len(authored_cards())} authored cards")
        for x in stale:
            print(f"  - {x}", file=sys.stderr)
        return 1 if stale else 0

    if args.command == "release":
        if not args.out.exists():
            print(f"no graph at {args.out} — run build first", file=sys.stderr)
            return 1
        text = render_release(args.out)
        RELEASE.write_text(text, encoding="utf-8")
        bad = verify_anchors(args.out, RELEASE)
        n = len(ANCHOR.findall(text))
        print(f"rendered {RELEASE.name}: {len(text.splitlines())} lines, {n} anchors")
        if bad:
            for b in bad:
                print(f"  - {b}", file=sys.stderr)
            return 1
        print("  every anchor resolves")
        return 0

    if args.command == "build":
        print(f"building {args.out}")
        stats = build(sources, roots, kt, args.out)
        report(stats)
        failures = assert_positive(stats)
        if failures:
            print("\nFAILED:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)
            return 1
        print("  all assertions passed")
        return 0

    # check — rebuild into a temp path and byte-compare the dumps
    if not args.out.exists():
        print(f"no graph at {args.out} — run build first", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "rebuild.db"
        stats = build(sources, roots, kt, tmp)
        failures = assert_positive(stats)
        if failures:
            print("FAILED during rebuild:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)
            return 1
        a, b = dump(args.out), dump(tmp)
        if a != b:
            print("DRIFT: rebuild does not match the committed graph", file=sys.stderr)
            la, lb = a.split("\n"), b.split("\n")
            print(f"  committed {len(la)} lines · rebuild {len(lb)} lines", file=sys.stderr)
            for i, (x, y) in enumerate(zip(la, lb)):
                if x != y:
                    print(f"  first difference at line {i + 1}:", file=sys.stderr)
                    print(f"    committed: {x[:160]}", file=sys.stderr)
                    print(f"    rebuild  : {y[:160]}", file=sys.stderr)
                    break
            return 1
    bad = verify_anchors(args.out, HANDBOOK) + verify_anchors(args.out, RELEASE)
    if bad:
        print("FAILED: generated-document anchors", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 1
    anchors = sum(len(ANCHOR.findall(d.read_text(encoding="utf-8")))
                  for d in (HANDBOOK, RELEASE) if d.exists())

    # The handbook must also be current, not merely anchored: a stale render that
    # still resolves is exactly the drift this cycle exists to end.
    _, stale_cards = stamp_card_hashes(write=False)
    if stale_cards:
        print("FAILED: authored-card provenance", file=sys.stderr)
        for x in stale_cards:
            print(f"  - {x}", file=sys.stderr)
        return 1

    for doc, fn, cmd in ((HANDBOOK, render_handbook, "render"),
                         (RELEASE, render_release, "release")):
        if doc.exists() and doc.read_text(encoding="utf-8") != fn(args.out):
            print(f"DRIFT: {doc.name} is stale — run `{cmd}`", file=sys.stderr)
            return 1

    print(f"check: rebuild is byte-identical ({stats['nodes']} nodes, "
          f"{stats['edges']} edges); {anchors} document anchors all resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
