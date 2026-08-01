---
format: ngf/0.0.3
kind: methodology
ai_card:
  id: kg-rag-cookbook-methodology
  kind: methodology
  audience: engineer
  status: active
  owner_area: /root/projects/kg-rag-cookbook
  title: "KG-RAG Specialist Framework — the methodology"
  version: "0.0.1"
  created: 2026-08-01
  owner_user: eyal_nof
  provides:
    - "The build loop, and why measurement sits inside it rather than after it"
    - "The validation gate: single-variable intervention against the target corpus"
    - "Defect-to-rule promotion, the mechanism that makes the framework improve"
    - "The labelling discipline, and the scale law that invalidates borrowed results"
    - "The framework's own first open task, stated as a falsifiable experiment"
  depends_on:
    - "glassbox-os/docs/eyals-complete-rag-source-of-truth-20260702.ngf.md — Claim 4, the delivery gate"
    - "kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md — 15 defects, the promotion record"
    - "kg-rag-toolkit/BUGS_AND_FIXES.md — the light-track promotion record"
edges:
  gate: "per-corpus single-variable validation"
  feeds: "COOKBOOK.ngf.md — every promoted rule becomes a recipe or an anti-pattern"
provenance:
  kind_spec_version: methodology/0.0.1
  content_hash: PENDING
  source_path: METHODOLOGY.ngf.md
  owner_user: eyal_nof
  law: "derivation-with-provenance, never fabrication"
---

# The methodology

> The framework's only real claim is procedural: **run the gate against your corpus, keep what
> improves, and label the rest honestly.** Everything else is technique.

---

## §1 · The loop

```
   declare ──> build ──> measure ──> promote
      ▲                                  │
      └──────────────────────────────────┘
```

Measurement is *inside* the loop. A build that has not been measured against its own corpus has not
finished, and the thing that comes out of measurement is not a score — it is a **rule**, promoted
back into the generator so the next build cannot repeat the defect.

---

## §2 · The gate — single-variable intervention

**L2: authority is not sufficient.** A technique validated elsewhere is a hypothesis here.

1. Build the baseline. Record the configuration exactly.
2. Change **one** variable.
3. Re-run the same queries with the same judge.
4. Classify: `IMPROVED` · `DEGRADED` · `NO EFFECT` · `NOT_ESTABLISHED`.
5. Keep only what improved. Log what degraded — that is a finding, not a waste.

`[OBSERVED]` Nine playbooks against a 12-node EU AI Act corpus: **2 validated, 6 degraded,
1 skipped.** All six that degraded had been genuinely validated at 278–4,890 nodes.

**Two rules that make results trustworthy:**

- **Single-variable only.** `[OBSERVED]` Multi-variable combinations are untested; interaction
  effects are unknown. Changing two things means you have measured nothing.
- **|Δ| < 0.02 is not a result.** `[OBSERVED]` Judge variance is ±0.02 run-to-run on identical
  input. Re-test before classifying anything inside that band.

---

## §3 · Defect-to-rule promotion

This is the mechanism that makes the framework compound rather than accumulate.

**A defect found in an instance is not fixed in the instance. It is promoted into the generator.**

Worked example — `[OBSERVED]` from the light track's `BUGS_AND_FIXES.md`:

> A `react-coding` agent on Android arm64 / Python 3.14 crashed at chunk **1200/1537** of a live
> ingest: `sqlite3.IntegrityError: UNIQUE constraint failed: entities.id`. The template declared
> `UNIQUE(type, name)` on a table whose `id` is deterministically derived from `(type, name)` — so
> the PRIMARY KEY fires first and `ON CONFLICT(type, name)` never triggers. Invisible until an
> entity appears in more than one chunk.
>
> Promoted to **SKILL.md Stage 5 as a canonical pattern**, plus an **anti-pattern** rejecting
> `UNIQUE(type,name)` on deterministic-ID tables. Resolved in plugin v0.2.0.

Promotion differs by track:

| Track | A defect becomes |
|---|---|
| Heavy | a template fix **and** a spec validation rule that rejects the shape |
| Light | a canonical pattern in `SKILL.md` **and** an explicit anti-pattern |

**Log the defect even after fixing it.** `kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md`
keeps resolved items with the note *"retained to document the exact failure modes future maintainers
should not reintroduce."* A fixed defect that is deleted from the record will be rebuilt.

**Defect schema** — every entry carries: `severity` · `category` · `symptom` · `root_cause` · `fix` ·
`verified_by` · `logged_as_pitfall_doc`.

**The strongest finding is a cross-project one.** `[OBSERVED]` The *same* silent-fallback-degradation
failure was found independently in two unrelated codebases — the scaffolder and a separate fusion
engine. A defect that recurs across projects is a **class**, and classes earn a pitfall doc.

---

## §4 · The scale law

`[OBSERVED]` **A playbook's success at corpus scale S₁ does not transfer to S₂ without
re-validation.** Six of nine techniques validated at 278–4,890 nodes degraded at 12 nodes.

Validated: **12 nodes**, and **278–4,890 nodes**.
Untested: **50–500**, and **>10K**. Client corpora typically land at 500–50K — i.e. mostly in the
untested band. Treat every number in this repo as scale-scoped, and say which scale.

---

## §5 · Labelling discipline

| Label | Means |
|---|---|
| `[OBSERVED]` | Measured on a stated corpus with a stated judge, `n` recorded |
| `[DERIVED]` | Follows from a document held, cited by path |
| `[DIRECTIONAL]` | Consistent trend, below significance at current `n` |
| `[NOT_ESTABLISHED]` | Tested, did not reach significance. **A result.** |
| `[SPECULATIVE]` | Judgment. No measurement behind it |

**Honest hedges are load-bearing (L4).** A hedge is removed only by *resolving* it with a
measurement — never by deletion. If new evidence weakens a load-bearing claim, update the claim and
add the new hedge; do not silently soften the old one.

**Documentation pattern.** Two sections: **Part 1** briefs the next writer on discipline and states
load-bearing claims that must not be softened; **Part 2** stands alone for a hostile reader. Every
empirical claim in Part 2 cites a reproducible harness and a path.

---

## §6 · The framework's own first open task

The methodology is only worth anything if it is applied to itself. So, stated as a falsifiable
experiment rather than a plan:

**Hypothesis.** `kg-tooling-expert`'s blind-query failure is caused by its `hash` embedder, not by
its corpus. Replacing the α leg with named-attribute contextual embeddings will lift the 20-query
blind-set hit rate materially above the ~90% that synonym enrichment reached, and will recover the
one query that **two rounds of enrichment failed to fix** (`dual-source-reconciliation-pattern`).

**Why it is plausible.** `[OBSERVED]` The corpus is discrete, declared items — the class
named-attribute embeddings are for. The upstream measurement is strong (95% Pass@10 vs VoyageAI's
92% at 1,791 nodes). The observed failure — natural phrasing sharing no keywords with a doc's jargon
— is exactly what a semantic α leg addresses and what BM25 structurally cannot.

**Protocol.** Single-variable: change only the embedder. Same corpus, same 20 blind queries, same
judge. Baseline is the current post-enrichment state, not the pre-enrichment one.

**Falsification.** If the blind-set hit rate does not improve beyond judge variance (±0.02), the
hypothesis is wrong: the limitation is in the corpus or the query set, not the embedding class.
`[NOT_ESTABLISHED]` either way until run.

**Status.** Not run. **No claim that this fix works may enter any document in this repo until it
has been.** The mechanism is sound and the upstream evidence is strong — and neither is a
measurement on this corpus.

---

## §7 · Choosing a track

| Situation | Track |
|---|---|
| Domain well-understood, build repeatable | **Heavy** — validation catches you |
| Hostile environment (Termux, exotic Python), or a new domain shape | **Light** — Claude adapts where a template breaks |
| Corpus < ~50 nodes | **Light**, and expect most playbooks to degrade (§4) |
| The agent must be regenerated by CI | **Heavy** — content-addressed spec |

Neither track exempts you from §2. The gate is the framework.
