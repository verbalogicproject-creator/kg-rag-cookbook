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


---

## §2 · Scope ledger

Every candidate carries a scope and, where it is not `IN`, a reason. Nothing is admitted for being adjacent to something admitted, and nothing is excluded by being forgotten — the source list is an explicit allowlist.


### IN — the monorepo (13)


| Package | Layer | Reason | Node |
|---|---|---|---|
| `claude-arch-inventory` | L0 | — | [[node:system::claude-arch-inventory]] |
| `corpus-guard` | L0 | — | [[node:system::corpus-guard]] |
| `declared_core` | L0 | — | [[node:system::declared_core]] |
| `rag_evaluator` | L0 | — | [[node:system::rag_evaluator]] |
| `universal_parser` | L0 | — | [[node:system::universal_parser]] |
| `NLKE-mud-detection` | L1 | — | [[node:system::NLKE-mud-detection]] |
| `declared_rules` | L1 | — | [[node:system::declared_rules]] |
| `frontmatter_rag` | L1 | — | [[node:system::frontmatter_rag]] |
| `kg_toolkit` | L1 | — | [[node:system::kg_toolkit]] |
| `ngfify` | L1 | — | [[node:system::ngfify]] |
| `NLKE-primitives-library` | L2 | — | [[node:system::NLKE-primitives-library]] |
| `project_memory` | L2 | — | [[node:system::project_memory]] |
| `kg-rag-pipeline` | L3 | — | [[node:system::kg-rag-pipeline]] |

### IN — specification and doctrine (4)


| Package | Layer | Reason | Node |
|---|---|---|---|
| `NLKE-high-dimensional-KG-RAG-Framework` | — | — | [[node:system::NLKE-high-dimensional-KG-RAG-Framework]] |
| `NLKE-kg-rag-contract` | — | — | [[node:system::NLKE-kg-rag-contract]] |
| `kg-rag-cookbook` | — | — | [[node:system::kg-rag-cookbook]] |
| `sag-declarum-atlas-framework` | — | — | [[node:system::sag-declarum-atlas-framework]] |

### DEFER — decide after the graph (3)


| Package | Layer | Reason | Node |
|---|---|---|---|
| `codebase-memorizer` | — | Scope overlaps /root/multi-graph-memory. Two memory systems must not both ship without a stated boundary. | [[node:system::codebase-memorizer]] |
| `context-os` | — | Adjacent format concern; relationship to .ngf.md not established. | [[node:system::context-os]] |
| `ctx-architecture` | — | Adjacent format concern; relationship to .ngf.md not established. | [[node:system::ctx-architecture]] |

### RETIRE — generation 1 (1)


| Package | Layer | Reason | Node |
|---|---|---|---|
| `flags` | — | — | [[node:system::flags]] |

---

## §3 · Layering

Derived from **18 measured cross-package import edges**, not asserted. The weight counts *files* in the importer that import the package.


| Importer | Imports | Files |
|---|---|---|
| `kg-rag-pipeline` | `NLKE-mud-detection` | 8 |
| `project_memory` | `declared_core` | 8 |
| `declared_rules` | `declared_core` | 7 |
| `frontmatter_rag` | `declared_core` | 6 |
| `kg_toolkit` | `declared_core` | 6 |
| `kg-rag-pipeline` | `declared_core` | 5 |
| `NLKE-mud-detection` | `declared_core` | 3 |
| `NLKE-primitives-library` | `frontmatter_rag` | 3 |
| `NLKE-primitives-library` | `NLKE-mud-detection` | 1 |
| `NLKE-primitives-library` | `declared_core` | 1 |
| `NLKE-primitives-library` | `ngfify` | 1 |
| `kg-rag-cookbook` | `frontmatter_rag` | 1 |
| `kg-rag-cookbook` | `kg_toolkit` | 1 |
| `kg-rag-pipeline` | `corpus-guard` | 1 |
| `kg-rag-pipeline` | `kg_toolkit` | 1 |
| `ngfify` | `universal_parser` | 1 |
| `project_memory` | `ngfify` | 1 |
| `project_memory` | `universal_parser` | 1 |

The package dependency graph is **acyclic**, so the monorepo can be assembled bottom-up with no circular-dependency work.


---

## §4 · The vendoring collapse


**8 vendored trees** are declared across 6 packages.


| Vendored | Digest | Copied into |
|---|---|---|
| `declared_core@0.1.0` | `blake2b:b1c4aa1c8fa709ba96…` | `NLKE-mud-detection`, `declared_rules`, `frontmatter_rag`, `kg_toolkit`, `project_memory` — **5** |
| `ngfify@0.2.1` | `blake2b:5ccf68667199653cc3…` | `project_memory` — **1** |
| `universal_parser@0.1.1` | `blake2b:35188233885ce618d9…` | `ngfify`, `project_memory` — **2** |

Every copy of a given package declares the same digest, and the upstream tree matches. Six trees of one package currently agree, held there by discipline alone. **That makes now the cheapest moment to collapse them** — unifying while they agree is a deletion; unifying after a divergence is a merge with no oracle for which side is right. [[node:finding::declared-core-vendored-five-times-in-sync]]


---

## §5 · Package inventory


| Package | Scope | Layer | .py | LOC | `def test_` | `.ngf.md` | Licence | Node |
|---|---|---|---|---|---|---|---|---|
| `rag_evaluator` | IN | L0 | 33 | 3,740 | 100 | 0 | **none** | [[node:system::rag_evaluator]] |
| `declared_core` | IN | L0 | 32 | 3,549 | 107 | 1 | Apache-2.0 | [[node:system::declared_core]] |
| `universal_parser` | IN | L0 | 30 | 2,912 | 58 | 0 | Apache-2.0 | [[node:system::universal_parser]] |
| `claude-arch-inventory` | IN | L0 | 32 | 2,514 | 29 | 0 | MIT | [[node:system::claude-arch-inventory]] |
| `corpus-guard` | IN | L0 | 11 | 1,228 | 22 | 0 | PROPRIETARY | [[node:system::corpus-guard]] |
| `kg_toolkit` | IN | L1 | 44 | 6,465 | 111 | 0 | Apache-2.0 | [[node:system::kg_toolkit]] |
| `NLKE-mud-detection` | IN | L1 | 43 | 5,959 | 56 | 0 | Apache-2.0 | [[node:system::NLKE-mud-detection]] |
| `declared_rules` | IN | L1 | 43 | 5,613 | 127 | 0 | Apache-2.0 | [[node:system::declared_rules]] |
| `ngfify` | IN | L1 | 65 | 5,477 | 115 | 4 | Apache-2.0 | [[node:system::ngfify]] |
| `frontmatter_rag` | IN | L1 | 45 | 4,775 | 73 | 0 | Apache-2.0 | [[node:system::frontmatter_rag]] |
| `project_memory` | IN | L2 | 113 | 18,415 | 422 | 4 | Apache-2.0 | [[node:system::project_memory]] |
| `NLKE-primitives-library` | IN | L2 | 14 | 4,618 | 14 | 400 | PROPRIETARY | [[node:system::NLKE-primitives-library]] |
| `kg-rag-pipeline` | IN | L3 | 29 | 5,780 | 92 | 1 | Apache-2.0 | [[node:system::kg-rag-pipeline]] |
| `kg-rag-cookbook` | SPEC | — | 17 | 3,400 | 6 | 5 | **none** | [[node:system::kg-rag-cookbook]] |
| `NLKE-kg-rag-contract` | SPEC | — | 2 | 993 | 0 | 1 | **none** | [[node:system::NLKE-kg-rag-contract]] |
| `NLKE-high-dimensional-KG-RAG-Framework` | SPEC | — | 1 | 769 | 0 | 26 | **none** | [[node:system::NLKE-high-dimensional-KG-RAG-Framework]] |
| `sag-declarum-atlas-framework` | SPEC | — | 4 | 641 | 0 | 82 | **none** | [[node:system::sag-declarum-atlas-framework]] |
| `context-os` | DEFER | — | 41 | 7,947 | 196 | 5 | Apache-2.0 | [[node:system::context-os]] |
| `codebase-memorizer` | DEFER | — | 22 | 4,552 | 63 | 0 | Apache-2.0 | [[node:system::codebase-memorizer]] |
| `ctx-architecture` | DEFER | — | 14 | 2,894 | 38 | 0 | Apache-2.0 | [[node:system::ctx-architecture]] |
| `flags` | RETIRE | — | — | 0 | — | 0 | **none** | [[node:system::flags]] |

**IN + SPEC totals: 558 Python files · 76,848 LOC · 1,332 test functions · 524 `.ngf.md` cards.**


---

## §6 · The v1.0.0 production-quality gate

Every row extracted. `?` is honest: this document cannot run a test suite, and a column of unknowns is not a pass.


| Package | README | CHANGELOG | LICENCE | NOTICE | CLAUDE.md | pyproject | Suite green |
|---|---|---|---|---|---|---|---|
| `NLKE-mud-detection` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `NLKE-primitives-library` | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ? |
| `claude-arch-inventory` | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ? |
| `corpus-guard` | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ | ? |
| `declared_core` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `declared_rules` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `frontmatter_rag` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `kg-rag-pipeline` | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ? |
| `kg_toolkit` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `ngfify` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `project_memory` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `rag_evaluator` | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ? |
| `universal_parser` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ? |
| `NLKE-high-dimensional-KG-RAG-Framework` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ? |
| `NLKE-kg-rag-contract` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ? |
| `kg-rag-cookbook` | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ? |
| `sag-declarum-atlas-framework` | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ? |

### Blockers


1. **5 in-scope packages have no LICENCE** — `NLKE-high-dimensional-KG-RAG-Framework`, `NLKE-kg-rag-contract`, `kg-rag-cookbook`, `rag_evaluator`, `sag-declarum-atlas-framework`. An unlicensed package cannot ship beside licensed ones. **Hard blocker.**

2. **The `Suite green` column is entirely `?`.** No suite was run. Per `absence-is-not-a-result`, a column of unknowns must never be rendered as a pass. [[node:doctrine_rule::absence-is-not-a-result]]

3. **`NLKE-primitives-library`, `corpus-guard` are PROPRIETARY** inside an otherwise open estate, and need a private tier whose boundary CI enforces — not a note in a README.


---

## §7 · Licence reconciliation


| Licence | Packages |
|---|---|
| Apache-2.0 | `NLKE-mud-detection`, `declared_core`, `declared_rules`, `frontmatter_rag`, `kg-rag-pipeline`, `kg_toolkit`, `ngfify`, `project_memory`, `universal_parser` |
| MIT | `claude-arch-inventory` |
| **none** | `NLKE-high-dimensional-KG-RAG-Framework`, `NLKE-kg-rag-contract`, `kg-rag-cookbook`, `rag_evaluator`, `sag-declarum-atlas-framework` |
| PROPRIETARY | `NLKE-primitives-library`, `corpus-guard` |

Stated, not blended. The monorepo declares Apache-2.0 at root; MIT packages keep their own LICENCE; proprietary packages live in a `private/` tier, and CI fails if a public package imports one. [[node:doctrine_rule::provenance]]


---

## §8 · Migration order

Leaves first, so nothing breaks mid-move. Waves follow the measured layering in §3.


| Wave | Packages | Gate |
|---|---|---|
| 0 | workspace scaffold, CI, `private/` tier, licence policy check | empty workspace builds |
| 1 | L0: `claude-arch-inventory`, `corpus-guard`, `declared_core`, `rag_evaluator`, `universal_parser` | suites green in the workspace |
| 2 | L1: `NLKE-mud-detection`, `declared_rules`, `frontmatter_rag`, `kg_toolkit`, `ngfify` | each suite green with no vendored copy present |
| 3 | L2: `NLKE-primitives-library`, `project_memory` | each suite green |
| 4 | L3: `kg-rag-pipeline` | each suite green |
| 5 | delete all 8 vendored trees; repoint to workspace dependencies | dependents green with no vendored copy on disk |
| 6 | spec repos and docs | format spec resolves; cross-links valid |

**The vendoring wave is the one that pays.** Everything before it is scaffolding.


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
