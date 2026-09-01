# KG-RAG Specialist Framework

Formalizes generators and instances that already exist elsewhere; nothing here is vendored or
duplicated. **As of 2026-09-01 it also ships one executable** — a builder that turns the estate
into a queryable graph, and generates two documents from it.

**Start at [`MANIFEST.ngf.md`](./MANIFEST.ngf.md).** If you are an AI session, read the manifest and
then [`BOOT.ngf.md`](./BOOT.ngf.md), and stop there until you have done what it says.

| Document | What it answers |
|---|---|
| [`MANIFEST.ngf.md`](./MANIFEST.ngf.md) | What exists, the four laws, the boundary |
| [`BOOT.ngf.md`](./BOOT.ngf.md) | Cold-start initiation for an AI session |
| [`SPECS.ngf.md`](./SPECS.ngf.md) | The declaration surface and conformance |
| [`METHODOLOGY.ngf.md`](./METHODOLOGY.ngf.md) | The loop and the validation gate |
| [`COOKBOOK.ngf.md`](./COOKBOOK.ngf.md) | Recipes, defects, anti-patterns |

## The graph

```bash
python3 TS-kg-rag-of-kg-rag.py build     # walk the declared allowlist, emit the graph
python3 TS-kg-rag-of-kg-rag.py render    # regenerate the handbook
python3 TS-kg-rag-of-kg-rag.py release   # regenerate the release specification
python3 TS-kg-rag-of-kg-rag.py stamp     # refill authored-card content hashes
python3 TS-kg-rag-of-kg-rag.py check     # the gate — see below
python3 TS-kg-rag-of-kg-rag.py stats     # node and edge counts
```

| Artifact | What |
|---|---|
| [`sources.json`](./sources.json) | The declared allowlist. Not a glob — a repo absent here is excluded, not missed |
| [`curated/`](./curated/) | The layer that needs reading intent: contradictions, supersessions, the doctrine map. Every entry carries an `evidence.source`, enforced by the loader |
| `TS-kg-rag-of-kg-rag.py` | The builder |
| `TS-kg-rag-of-kg-rag.db` | The graph |
| [`TS-kg-rag-of-kg-rag.md`](./TS-kg-rag-of-kg-rag.md) | The handbook — **generated**, do not edit |
| [`NLKE-production-quality-release-V1.0.0.md`](./NLKE-production-quality-release-V1.0.0.md) | Monorepo unification spec — **generated**, do not edit |

`check` fails if any of these is true: the graph does not rebuild byte-identically, a `[[node:…]]`
anchor in a generated document does not resolve, a generated document is stale, or an authored
card's `content_hash` no longer matches its body. It also fails if the anchor count is zero —
a check that passes by finding nothing has reported nothing.

**Run order after any edit:** `build` → `render` → `release` → `stamp` → `check`. The graph
includes this repository in its own source list, so editing the builder changes the graph.
