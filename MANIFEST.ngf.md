---
format: ngf/0.0.3
kind: framework_manifest
ai_card:
  id: kg-rag-cookbook-manifest
  kind: framework_manifest
  audience: engineer
  status: active
  owner_area: /root/projects/kg-rag-cookbook
  title: "KG-RAG Specialist Framework — the manifest"
  version: "0.0.1"
  created: 2026-08-01
  owner_user: eyal_nof
  provides:
    - "What the framework is, and the four laws that govern it"
    - "The complete component inventory across both tracks and both filesystems"
    - "What is IN scope and what is explicitly OUT"
    - "The read-order for every other document here"
  depends_on:
    - "glassbox-os/docs/eyals-complete-rag-source-of-truth-20260702.ngf.md — the methodology SOT"
    - "kg-tooling-expert/playbook/ — 933 lines, 15 logged defects"
    - "scaffold_kg_rag_agent — the heavy-track generator"
    - "kg-rag-toolkit (Termux) — the light-track generator"
edges:
  formalizes: "the KG-RAG specialist framework — one declaration, two generators"
  supersedes_partial: "any claim that the heavy and light tracks are competing approaches"
  gate: "per-corpus empirical validation — authority is not sufficient"
provenance:
  kind_spec_version: framework_manifest/0.0.1
  content_hash: sha256:ce3ebf465f9d47e4086a7b38f06173d169d29ddd726c8418d547cffd801d373a
  source_path: MANIFEST.ngf.md
  owner_user: eyal_nof
  law: "derivation-with-provenance, never fabrication"
---

# KG-RAG Specialist Framework — manifest

> **What this is.** A framework for building domain-specific knowledge-graph RAG agents whose
> retrieval quality is *declared, measured, and honestly labelled* — not asserted.
>
> **What it is not.** A RAG tutorial. Every claim here is anchored to a measurement or a logged
> defect from a real build, with a path you can open.

---

## §1 · The four laws

These govern every document in this repo and every agent built from it.

**L1 · Declare before you emit.** The dimension schema, the entity/relation schema, the eval
queries, and the retrieval configuration are all declared artifacts before a single document is
ingested. A retriever whose behaviour is not declared cannot be validated.

**L2 · Authority is not sufficient — the gate is per-corpus empirical validation.** A playbook that
worked on corpus A is a *hypothesis* about corpus B. `[OBSERVED]` Nine playbooks were tested against
a 12-node EU AI Act corpus with single-variable interventions: **2 validated, 6 degraded, 1 skipped.**
Six techniques that were genuinely validated at 278–4,890 nodes made things *worse* at 12 nodes.

**L3 · Interpretability over opacity.** Where a choice exists between a signal you can explain and
one you cannot, take the explainable one — provided it measures at least as well. Named-attribute
embeddings exist because "why did these two match?" must have an answer.

**L4 · Honest hedges are load-bearing.** A hedge may only be removed by *resolving* it with a
measurement, never by deleting it. A finding labelled `NOT_ESTABLISHED` is a result, not a failure.

---

## §2 · The thesis

**One declaration, two generators.**

```
declaration  (domain · dimensions · KG schema · retrieval config · eval gate)
      │
      ├── heavy track ──> scaffold_kg_rag_agent (pip)    → validated templates, AgentSpec
      └── light  track ──> kg-rag-toolkit (SKILL.md)     → canonical patterns applied by Claude
```

The two tracks are **not competitors**. They differ in *where correctness lives*:

| | Heavy track | Light track |
|---|---|---|
| Artifact | pip package, `scaffold_kg_rag_agent` v1.0.0a1 | Claude Code plugin, `kg-rag-toolkit` v0.2.0 |
| Declaration | `AgentSpec` — closed, validated, content-addressed (`spec-<blake2b12>`) | `SKILL.md` stages + a written plan file |
| Correctness lives in | schema validation + templates | canonical patterns + anti-patterns, applied with judgment |
| Fails by | rejecting an invalid spec before writing a file | Claude misreading a pattern |
| Proven on | `tonejs-expert`, `kg-tooling-expert` | a `react-coding` agent on Android arm64 / Python 3.14 |
| Best when | the domain is well-understood and repeatable | the environment is hostile or the domain is new |

**Both feed one loop.** A defect found in an instance is promoted into the generator so it cannot
recur — as a template fix and a validation rule on the heavy side, as a canonical pattern plus an
anti-pattern on the light side. See `METHODOLOGY.ngf.md` §3.

---

## §3 · Component inventory

Nothing below is moved or vendored by this repo. This is a map, and every path is real.

### Generators

| Component | Path | State |
|---|---|---|
| `scaffold_kg_rag_agent` | `/root/projects/scaffold_kg_rag_agent` | v1.0.0a1; 9-chapter docs `00`–`08` |
| `kg-rag-toolkit` (light) | `~/kg-rag-toolkit` *(Termux)* | v0.2.0 plugin, 2 skills, own `BUGS_AND_FIXES.md` |
| `kg-rag-toolkit` (mirror) | `/root/projects/future/kg-rag-toolkit` | plugin copy |

### Instances — the evidence base

| Instance | Path | What it proves |
|---|---|---|
| `tonejs-expert` | `/root/projects/tonejs-expert` | Instance #1; source of the `kg.py` port |
| `kg-tooling-expert` | `/root/projects/kg-tooling-expert` | Self-referential: a KG-RAG specialist *about* KG-RAG. 46 patterns, 19 prior-art, 5 case-studies, 3 schema-examples; **15 logged defects** |
| `react-coding` | Termux, per `BUGS_AND_FIXES.md` | The light track on hostile hardware |
| `openai-cookbook-kg-rag` | `~/openai-cookbook-kg-rag` *(Termux)* | A third domain |

### Methodology and measurement

| Component | Path | Role |
|---|---|---|
| **RAG source-of-truth** | `~/glassbox-os/docs/eyals-complete-rag-source-of-truth-20260702.ngf.md` | **The upstream authority.** 4 load-bearing claims, 7 honest hedges |
| `glassbox-os` | `~/glassbox-os` *(Termux)* | 11-layer eco-system; owns the named-attribute invariant and `dimensions/*.json` |
| `kg-rag-pipeline` | `/root/projects/kg-rag-pipeline` | The measurement engine — one engine, two corpora, one gate |
| `rag_evaluator` | `/root/projects/rag_evaluator` | Eval harness *(closed track)* |
| `gemini-stack` | `~/sdk-agent/gemini-web-searcher-stack-updater.py` | 250-line single file, 3 modes; the simplicity proof |

---

## §4 · The retrieval stack

```
score(item, query) = α · cos(e_item, e_query) + β · BM25(item, query) + γ · graph(item, query)
```

The α leg's embedding **class** determines the whole weight distribution. This is the single most
consequential decision in the framework, and it is empirical, not preference:

| Embedding class | α | β | γ | Measured |
|---|---|---|---|---|
| Semantic-quality (contrastive-trained, `gemini-embedding-2`, **named-attribute**) | 0.40 | 0.45 | 0.15 | 88.5% recall @ 278 nodes |
| Hash / bootstrap | 0.20 | 0.65 | 0.15 | 95.6% recall @ 4,890 nodes |

`[OBSERVED]` **Applying semantic weights to hash embeddings collapses recall to 15%.** The weights
are not tunable preferences; they are a function of what the α leg can actually carry.

**Named-attribute contextual embeddings** are the framework's default α leg: Claude scores each
item against a declared dimension schema at index time, yielding an interpretable vector in
`[0,1]^d` with `d` typically 20–70. `[OBSERVED]` 56 Claude-scored dimensions reached **95% Pass@10,
beating VoyageAI's 1024-dim at 92%** on the same 1,791-node corpus.

They are **not** a universal replacement. See `SPECS.ngf.md` §5 for the boundary.

---

## §5 · Scope

**In scope.** Declared-domain corpora of discrete items — docs, code nodes, KG entries, tools,
components, regulatory provisions. Corpora from roughly 10 to 50,000 nodes. Agents exposing a CLI
and optionally MCP. English.

**Out of scope, explicitly.** `[DERIVED from the RAG SOT §8]` Open-domain search, cross-language
semantic search at scale, and arbitrary long-form deduplication. **Neural embeddings remain the
correct tool for those.** This is a boundary, not a competition.

**Untested, therefore unclaimed.** Hebrew corpora (falsification test F6b scoped, not run).
Intermediate scales 50–500 nodes. Scales above 10K nodes. Multi-variable playbook combinations —
Sprint 0 was single-variable-only by design, so interaction effects are unknown.

---

## §6 · Read order

1. **`MANIFEST.ngf.md`** — this file. What exists and what governs it.
2. **`BOOT.ngf.md`** — if you are an AI session starting cold, read this second and stop there until you have done what it says.
3. **`SPECS.ngf.md`** — the declaration schemas and the conformance contract.
4. **`METHODOLOGY.ngf.md`** — how to run the loop, and the gate.
5. **`COOKBOOK.ngf.md`** — the recipes, the defects, the anti-patterns.

Upstream, when this repo is not enough: the RAG source-of-truth in `glassbox-os`, then
`kg-tooling-expert/playbook/`.

---

## §8 · The graph — added 2026-09-01

The framework acquired an executable and a corpus of its own. `TS-kg-rag-of-kg-rag.py` walks a
declared allowlist of the estate and emits a knowledge graph whose *domain is the estate's own
retrieval systems*; `TS-kg-rag-of-kg-rag.md` and `NLKE-production-quality-release-V1.0.0.md` are
generated from it, and neither can drift from it undetected.

**Why it exists.** Every finding in the estate was true when written and none of it was queryable,
so the same context had to be re-explained at the start of every session. The graph answers, with
citations: *where do my own systems disagree, and which side has evidence?*

### What it recorded that was not previously written down

| | |
|---|---|
| **8 contradictions** | four incompatible fusion formulas; six mutually inconsistent dimension counts |
| **5 supersessions** | what generation 2 replaced, and the measurement that justified it |
| **6 doctrine rules** | four were written as cards; two had to be named — see below |
| **acyclic package graph** | 18 measured import edges — the monorepo can assemble bottom-up |
| **8 vendored trees** | `declared_core` exists six times over, currently in agreement |

### Two rules the estate was already following without naming

Twenty-three of fifty-six findings answered to none of L1–L4 or to any of the four doctrine cards.
Thirteen of them needed rules that existed in the estate's *code and contracts* but had never been
written as doctrine:

**`authority`** — knowing what something is does not confer permission to act on it, and issuing a
directive is not performing it. Already stated in `kg-rag/recipe-registry.json`'s `proof_limit`, in
`multi-graph-memory`'s approval-free `ModelContextPort`, and in the runtime primitives.

**`provenance`** — a copy of a fact has no expiry date. Already the whole thesis of
`NLKE-kg-rag-contract` and the reason `VENDORED.json` carries digests.

> **Terminology, resolved.** `L2 · Authority is not sufficient` and the doctrine rule `authority`
> use the same word for different things. **L2 is epistemic** — a playbook's say-so is not evidence,
> and the gate is per-corpus validation. **`authority` is about permission** — grounding does not
> license action. Both stand; neither renames the other. When it matters, say *L2* or
> *rule `authority`*.

### The framework's own provenance, closed

All five cards carried `content_hash: PENDING` while declaring
`law: "derivation-with-provenance, never fabrication"`. A provenance field that is never filled is a
decoration. They now carry a real body digest, and `TS-kg-rag-of-kg-rag.py check` fails on a stale
one — `stamp` refills them.

---

## §7 · Status

`[SUPERSEDED 2026-09-01]` ~~This repo is documentation. It ships no code and generates nothing on
its own.~~ **No longer true.** It ships `TS-kg-rag-of-kg-rag.py`, and generates a knowledge graph
plus two documents from it. See §8.

`[OBSERVED]` It still formalizes generators that already exist and instances that already run —
that part stands. What changed is that the framework now has an executable of its own.

`[NOT ESTABLISHED]` That the named-attribute α leg fixes `kg-tooling-expert`'s measured
blind-query failure. The mechanism is right and the upstream measurement is strong, but **it has
not been run on this corpus.** That is the framework's own first open task — see
`METHODOLOGY.ngf.md` §6.
