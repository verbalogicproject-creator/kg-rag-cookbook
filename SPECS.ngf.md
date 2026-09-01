---
format: ngf/0.0.3
kind: framework_spec
ai_card:
  id: kg-rag-cookbook-specs
  kind: framework_spec
  audience: engineer
  status: active
  owner_area: /root/projects/kg-rag-cookbook
  title: "KG-RAG Specialist Framework — the formalization"
  version: "0.0.1"
  created: 2026-08-01
  owner_user: eyal_nof
  provides:
    - "The declaration surface: what a conforming agent must declare, and the legal values"
    - "The dimension-schema spec for named-attribute embeddings"
    - "The retrieval contract, including the two measured weight configurations"
    - "The conformance checklist — what makes an agent booted, not merely built"
    - "Two specification defects found in the current heavy-track spec"
  depends_on:
    - "scaffold_kg_rag_agent/docs/02-the-spec.md — the AgentSpec surface as built"
    - "glassbox-os/dimensions/*.json — worked dimension schemas"
    - "kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md — the measured defects"
edges:
  formalizes: "AgentSpec + dimension schema + retrieval config as one declaration"
  gated_by: "the conformance checklist in §7"
provenance:
  kind_spec_version: framework_spec/0.0.1
  content_hash: sha256:7a66c679220245ff7b65da2c9de9d0c28a7aee211004a7cd5205a88efee4b398
  source_path: SPECS.ngf.md
  owner_user: eyal_nof
  law: "derivation-with-provenance, never fabrication"
---

# The formalization

> A conforming KG-RAG agent is defined by what it **declares**, not by what it contains. This
> document is the declaration surface.

---

## §1 · The declaration, in four parts

```
declaration
├── agent      — domain, sources, tool surface           (AgentSpec)
├── dimensions — the named attributes Claude scores against
├── schema     — entities and relations
└── retrieval  — embedding class, fusion weights, eval gate
```

`[OBSERVED]` The heavy track implements **part 1 only** as a validated object. Parts 2–4 exist as
convention, config files, and prose. Closing that gap is the framework's principal specification
work — see §8.

---

## §2 · Part 1 — `AgentSpec` (as built)

From `scaffold_kg_rag_agent/docs/02-the-spec.md`. Closed, validated, content-addressed: an invalid
spec raises `SpecError` **before any file is written**, and `spec_hash()` returns
`spec-<blake2b12>`.

| Field | Legal values | Default |
|---|---|---|
| `domain` *(required)* | any string → slug | — |
| `sources` | `local_files` · `markdown` · `frontmatter` · `json` · `web` · `github` · `api` | `local_files, markdown` |
| `retrieval` | `vector` · `hybrid` · `kg_augmented` · `graph_only` | **`kg_augmented`** ⚠ see §3 |
| `kg_schema` | `generic` · `code_aware` · `doc_versioning` · `custom` | `generic` |
| `custom_entities` / `custom_relations` | `lower_snake_case` (when `kg_schema=custom`) | — |
| `eval_style` | `golden` · `llm_judge` · `both` | `golden` |
| `mcp_tools` | generic tools + the 7 asks | `search_kg, get_doc, kg_stats` |
| `embedder` | `hash` · `none` · `http` (+ `embed_url`) | **`hash`** ⚠ see §4 |

**Tool surface.** Generic: `search_kg`, `get_doc`, `kg_stats`, `find_exemplar`, `get_impact`,
`list_dimensions`. The **NLKE 7-ask surface**: `can_i`, `how_do_i`, `how_does_connect`, `route`,
`snapshot`, `what_for`, `why_not` — a question-shaped set carried forward from the declarum coding
model. The MCP server exposes **only** declared tools; the CLI `ask` verb always offers all seven.

---

## §3 · Specification defect 1 — the default retrieval mode is the broken one

`[OBSERVED]` `retrieval` defaults to `kg_augmented`. Logged defect #2 in
`kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md` records that mode as **severity: high,
measurably wrong top-1 results**:

> `retrieval.py::_augment()` expands top-k seeds' graph neighbours and RRF-fuses them back in at a
> **flat score of 1.0 each**, ranked only by iteration/alphabetical order — no relevance signal.
> A document that ranked #1 under `hybrid` **dropped out of the top-5 entirely** under `kg_augmented`.

The fix applied in both instances was to declare `retrieval: "hybrid"` and move graph traversal into
resolve-and-traverse custom tools instead.

**Required change.** Default `retrieval` to `hybrid`. Keep `kg_augmented` legal but require an
explicit opt-in, since flat-score fusion is only safe on a sparse graph. Until that lands, **every
spec must declare `retrieval` explicitly** — never rely on the default.

---

## §4 · Specification defect 2 — the recommended α leg cannot be declared

`[OBSERVED]` `embedder` accepts `hash`, `none`, `http`. There is **no `named_attribute` value.**

So the heavy-track spec cannot express the embedding class the methodology names as its default,
and every generated agent lands on `hash` — the weakest α leg — by default. That is the direct
mechanical cause of `kg-tooling-expert`'s blind-query failure (`COOKBOOK.ngf.md` §2).

**Required change.**

```
embedder: hash | none | http | named_attribute
    named_attribute requires: dimensions_path, scorer, dimension_count
```

---

## §5 · Part 2 — the dimension schema

A **named-attribute contextual embedding** for item `i` is a vector `e_i ∈ [0,1]^d` where every
dimension is a *declared, human-readable attribute* and the score is produced by an LLM reading the
item — not by a neural encoder.

```jsonc
{
  "schema_version": "dimensions/0.1",
  "domain": "kg-tooling",
  "scorer": "claude",
  "dimensions": [
    { "name": "retrieval_relevance",
      "question": "How central is retrieval ranking to this item?",
      "scale": "0.0 = unrelated … 1.0 = the item's whole subject" }
  ]
}
```

**Constraints.**

- `d` between **20 and 70**. `[OBSERVED]` 56 dimensions reached 95% Pass@10, beating VoyageAI's
  1024-dim at 92% on the same 1,791-node corpus. Below ~20 the vector cannot separate; far above 70
  the scorer's attention thins and index cost rises without measured benefit.
- Each dimension declares a `question` and a `scale`. A dimension a scorer cannot answer
  consistently is not a dimension.
- Vectors are **L2-normalized** before cosine.
- `[OBSERVED]` **Adding or reordering dimensions invalidates every existing `.npz`.** Re-index
  everything. Dimension order is part of the contract; treat the schema as append-only-with-reindex.

**Why this class.** Interpretability is mechanical, not aesthetic: the dimensions with the highest
joint score *are* the reason two items matched. You cannot ask that of a 1024-dim neural vector.

**The boundary — do not cross it.** `[DERIVED from RAG SOT §8]` Named-attribute embeddings are
**not** the right tool for open-domain search, cross-language semantic search at scale, or arbitrary
long-form deduplication. Neural embeddings remain correct there. A framework that claims otherwise
is overselling.

---

## §6 · Part 4 — the retrieval contract

```
score = α · cos(e_item, e_query) + β · BM25(item, query) + γ · graph(item, query)
```

Two configurations, both measured. `[OBSERVED]`

| Config | Embedding class | α | β | γ | Evidence |
|---|---|---|---|---|---|
| **1** | semantic-quality (contrastive, `gemini-embedding-2`, named-attribute) | 0.40 | 0.45 | 0.15 | 88.5% recall @ 278 nodes |
| **2** | hash / bootstrap | 0.20 | 0.65 | 0.15 | 95.6% recall @ 4,890 nodes |

**Config 1 weights on hash embeddings drops recall to 15%.** The weights follow the embedding class;
choosing them by taste is a category error.

**Fusion topology.** Prefer **RRF** over weighted-average on small dense corpora. `[OBSERVED]` 12-node
EU AI Act corpus, 30-query holdout: `0.7333` (weighted-avg, no edges) → `0.8333` (RRF + 19 declared
cross-reference edges). RRF rewards rank *agreement* between symbolic and semantic legs; weighted
average re-blends the noise that agreement eliminates.

**Caveat that must travel with any single run.** `[OBSERVED]` Judge variance is **±0.02** run-to-run
(Gemini-3.5-flash: 0.8167 then 0.8333, same corpus, same queries). **Any verdict on |Δ| < 0.02
requires re-testing before classification.**

---

## §7 · Conformance — what makes an agent *booted*

An agent conforms when all seven hold. Anything less is built, not booted.

| # | Requirement | Check |
|---|---|---|
| 1 | Declaration is complete and validated | spec validates; `spec_hash()` recorded |
| 2 | `retrieval` declared **explicitly** | never inherited from the default (§3) |
| 3 | Embedding class matches the weight config | §6 — mismatch is a hard fail |
| 4 | Dimension schema declared if `embedder=named_attribute` | `d ∈ [20,70]`, every dim has `question` + `scale` |
| 5 | Eval gate exists and has been **run on this corpus** | not inherited from another corpus (L2) |
| 6 | Eval includes queries the builder did **not** author | §8 — the blind set |
| 7 | Findings labelled `OBSERVED` / `DIRECTIONAL` / `NOT_ESTABLISHED` | with `n` and the judge |

---

## §8 · The blind-set requirement

Requirement 6 is the one the framework learned the hard way and the one most likely to be skipped.

`[OBSERVED]` `kg-tooling-expert`'s golden eval reported `recall@k = 1.0, MRR = 1.0`. An independent
agent with no visibility into corpus internals then wrote 20 realistic queries: **9 of 20 failed** to
surface a clearly on-topic existing doc in the top 3. One never appeared in the top 10 at all.

The playbook's own diagnosis: the golden eval measured queries *the builder had hand-verified
against the live retriever*. It measured memorization, not generalization.

**Therefore:** a golden eval authored by the builder is a regression test, never evidence of
retrieval quality. Every conforming agent carries a **blind set** — at minimum 20 queries authored
without visibility into the corpus — and reports its score separately from the golden set.

---

## §9 · Open specification work

| # | Item | Blocking |
|---|---|---|
| 1 | Default `retrieval` → `hybrid` (§3) | every new agent inherits a measured defect |
| 2 | Add `embedder: named_attribute` (§4) | the recommended α leg is undeclarable |
| 3 | Promote the dimension schema to a validated object | currently convention only |
| 4 | Promote the retrieval contract into the spec, with a class↔weights invariant | mismatch is silently legal |
| 5 | Make the blind set a spec field, not a habit | requirement 6 has no enforcement |
