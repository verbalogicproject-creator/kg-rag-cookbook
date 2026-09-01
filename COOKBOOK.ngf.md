---
format: ngf/0.0.3
kind: cookbook
ai_card:
  id: kg-rag-cookbook-recipes
  kind: cookbook
  audience: engineer
  status: active
  owner_area: /root/projects/kg-rag-cookbook
  title: "KG-RAG Specialist Framework — the cookbook"
  version: "0.0.1"
  created: 2026-08-01
  owner_user: eyal_nof
  provides:
    - "Seven recipes, each with the failure it prevents"
    - "The defect catalogue — real bugs from real builds, with root causes"
    - "The anti-pattern list: shapes to reject on sight"
    - "The frontmatter contract corpus docs must satisfy"
  depends_on:
    - "kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md — 15 logged defects, the full record"
    - "kg-tooling-expert/playbook/custom-query-tool-playbook.ngf.md — the custom-tool recipe"
    - "kg-rag-toolkit/BUGS_AND_FIXES.md — light-track defects from an Android arm64 build"
edges:
  derived_from: "measured defects in tonejs-expert, kg-tooling-expert, react-coding"
  governed_by: "METHODOLOGY.ngf.md §2 — nothing here is exempt from the gate"
provenance:
  kind_spec_version: cookbook/0.0.1
  content_hash: sha256:8a78645dee64dcde4c9f0cb8953509e9d58a9cf5ed62528c0780e20f4759b546
  source_path: COOKBOOK.ngf.md
  owner_user: eyal_nof
  law: "derivation-with-provenance, never fabrication"
---

# The cookbook

> Every recipe names the failure it prevents, and every failure listed here **actually happened** on
> a real build. Where a recipe is unproven on your corpus, it says so.

---

## §1 · Recipe — build an agent

**Heavy track.**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../scaffold_kg_rag_agent
.venv/bin/scaffold-kg-rag-agent init --spec spec/<domain>.spec.json --out agent/
.venv/bin/python3 scripts/build_corpus_docs.py
cd agent && ../.venv/bin/python3 <domain>-agent.py ingest --reset
```

**Declare `retrieval` explicitly.** Never inherit the default — it is `kg_augmented`, which is the
measured-broken mode (§2 defect D2, `SPECS.ngf.md` §3).

**Light track.** `/scaffold-kg-rag-agent` → structured interview (2 batches × ~3 questions) → plan
file at `.claude/plans/kg-rag-<domain>.md` → approval → scaffold. Prefer this on hostile hardware;
`[OBSERVED]` it produced a working agent on Android arm64 / Python 3.14 where templates broke.

**Danger.** `[OBSERVED]` `kg.py` and `asks.py` in a generated agent are **hand-edited generated
files**. Re-running `init --overwrite` destroys both. Diff first, always.

---

## §2 · Recipe — choose the retrieval mode

| Mode | Use when | Do not use when |
|---|---|---|
| `hybrid` | **Default. Start here.** | — |
| `vector` | α leg is semantic-quality and the corpus has no useful graph | hash embedder |
| `graph_only` | traversal *is* the query | free-text search matters |
| `kg_augmented` | graph is **sparse** and you have re-measured | dense graph — see below |

`[OBSERVED]` **D2 — `kg_augmented` floods ranking with flat-scored graph noise.** Severity: high.
`retrieval.py::_augment()` expands top-k seeds' neighbours and RRF-fuses them back at a **flat score
of 1.0 each**, ordered only by iteration/alphabet — no relevance signal at all. On a densely
connected custom-schema graph this drowns the real ranking: a document that ranked **#1** under
`hybrid` **fell out of the top-5 entirely**.

Fix: declare `hybrid`, and move traversal into explicit resolve-and-traverse custom tools where it
is a deliberate operation rather than an implicit ranking contaminant.

---

## §3 · Recipe — the semantic α leg *(the fix for keyword blindness)*

**The failure it prevents.** `[OBSERVED]` **D9 — keyword retrieval genuinely misses naturally-phrased
queries.** 20 realistic queries from an independent agent; **9 of 20** failed to surface a clearly
on-topic existing doc in the top 3. `"retrieval quietly failing instead of throwing an error"` did
not surface `silent-fallback-degradation-pitfall` **in the top 10** — a near-verbatim topic match.

Root cause: BM25 + hash-embedding hybrid is keyword matching. A user's phrasing often shares *no
exact tokens* with a doc's internal jargon, and nothing in that stack bridges the gap.

**The cheap mitigation, and its ceiling.** Enrich `entities:` frontmatter with natural-language
synonyms beside the jargon — e.g. `atomic-decomposition-pattern` gains *"break down documents"*,
*"small facts"*, *"decompose into atomic facts"* next to `composite_node`. Content-only, zero code.
`[OBSERVED]` 7/9 fixed immediately; ~55% → ~90% on the blind set. **One query still misses after two
rounds.** This is a mitigation, not a fix — BM25 can only match vocabulary physically present in the
indexed text.

**The actual fix.** Replace the α leg with **named-attribute contextual embeddings**: Claude scores
each item against a declared dimension schema at index time (`SPECS.ngf.md` §5), yielding an
interpretable `[0,1]^d` vector with `d ∈ [20,70]`. Then switch to Config 1 weights —
**α=0.40 / β=0.45 / γ=0.15**.

`[OBSERVED]` upstream: 56 Claude-scored dimensions → **95% Pass@10, beating VoyageAI's 1024-dim at
92%** on 1,791 nodes.
`[NOT_ESTABLISHED]` on any corpus in this framework. **Run the experiment in
`METHODOLOGY.ngf.md` §6 before citing this as a fix here.**

**Do not** switch weights without switching the embedding class. `[OBSERVED]` Config 1 weights on
hash embeddings drops recall to **15%**.

---

## §4 · Recipe — the blind set

The single highest-value hour in the whole framework.

1. Have an **independent agent** — no visibility into corpus internals — write ≥20 realistic queries
   in the voice of a real user.
2. Run them. Record top-3 and top-10 hit rates **separately** from the golden set.
3. Every miss is a defect. Triage: missing doc, missing vocabulary, or wrong retrieval class.
4. Report blind and golden separately, forever.

**Why.** `[OBSERVED]` `kg-tooling-expert`'s golden eval read `recall@k=1.0, MRR=1.0` while the blind
set failed 9/20. The golden set measured queries the builder had hand-verified **against the live
retriever** — memorization, not generalization. A builder-authored golden eval is a regression test.
It is never evidence of retrieval quality.

---

## §5 · Recipe — add a custom query tool

Full recipe: `kg-tooling-expert/playbook/custom-query-tool-playbook.ngf.md` §5. Shape:

1. Add the doc to `corpus/patterns/` following the frontmatter contract (§7).
2. Rebuild: `build_corpus_docs.py` → `ingest --reset`.
3. Add the function to `CUSTOM_ASKS` in `agent/kg_tooling/asks.py`.
4. Add a pinned test asserting the tool finds the thing it exists to find.
5. Re-run the blind set — a new tool can shift ranking for unrelated queries.

`[OBSERVED]` **D8 — "connected-to-X" checks must also check "IS X" first.** A relevance check that
walks edges from X can omit X itself. Easy to skip because it feels too obvious to need checking —
which is exactly why it was missed. Pinned in
`test_anti_patterns_finds_pitfall_asked_about_directly`.

---

## §6 · Recipe — run the gate

Per `METHODOLOGY.ngf.md` §2: baseline → **one** variable → same queries, same judge → classify →
keep or log. `|Δ| < 0.02` is judge noise, not a result.

Do **not** import another corpus's playbook results. `[OBSERVED]` 6 of 9 techniques validated at
278–4,890 nodes degraded at 12 nodes.

---

## §7 · The frontmatter contract

Corpus docs are the retrieval surface. Fields that matter most:

- **`entities:`** — the strongest lever you own. Include jargon **and** natural-language synonyms
  (§3). This field is the difference between a doc being findable and being invisible.
- **`id`, `kind`, `status`, `owner_area`** — identity and filtering.
- **relations** — declared, and **direction-consistent**. Pick a direction convention and enforce
  it; mixed directions silently corrupt traversal.

---

## §8 · Defect catalogue

Real defects from real builds. Full record: `kg-tooling-expert/playbook/bugs-gaps-and-fixes.ngf.md`
(15 entries) and `kg-rag-toolkit/BUGS_AND_FIXES.md`. Detailed here are those verified by reading.

| ID | Severity | Defect | Root cause | Status |
|---|---|---|---|---|
| **D2** | high | `kg_augmented` floods ranking | neighbours RRF-fused at flat 1.0, no relevance signal | fixed by declaring `hybrid` |
| **D3** | medium | Title resolves to a mid-document heading | `re.search(r"^#\s+…", MULTILINE)` matches the first `#` **anywhere** | `re.match` + filename-stem fallback |
| **D8** | medium | "connected-to-X" misses X itself | relevance walked edges without checking identity | pinned test |
| **D9** | high | Natural-phrasing queries miss on-topic docs | keyword-only α leg | mitigated to ~90%; **real fix in §3** |
| **L1.0** | blocker | `IntegrityError` at chunk 1200/1537 | `UNIQUE(type,name)` on a deterministic-`id` table — PK fires first, `ON CONFLICT(type,name)` never triggers | promoted to SKILL.md Stage 5, plugin v0.2.0 |
| **X1** | high | **Silent fallback degradation** | retrieval degrades quietly instead of raising | **cross-project class** — found independently in two unrelated codebases |
| **X2** | medium | Computed-but-unused centrality signal | signal calculated, never read | in the fusion engine |

### Added 2026-09-01 — found while building `TS-kg-rag-of-kg-rag.db`

Each verified by re-running the check that found it; commands are in the finding's
`evidence.source` in the graph.

| ID | Severity | Defect | Root cause | Status |
|---|---|---|---|---|
| **X1c** | high | `PRAGMA foreign_keys = ON` while **no table declares a foreign key** | the pragma enforces nothing on its own; referential integrity was assumed from its presence | `multi-graph-memory` — X1 class, 3rd codebase |
| **X1d** | high | A dangling graph reference is **skipped, not reported** | `exporter.ts:179` correctly declines to invent a node, then says nothing | `multi-graph-memory` — X1 class, 4th codebase; closed by `src/kg/integrity.ts` |
| **D10** | high | Cycle check **raises instead of answering** on deep graphs | `_find_cycle` recurses once per node; 50,000-node chain → `RecursionError` against CPython's limit of 1000 | `kg_toolkit`; TS port is iterative, tested at that depth |
| **D11** | medium | A graph cannot be byte-compared | `store.py:37` stamps `datetime.now()` into `created_at` on every row, so identical builds differ | `kg_toolkit`; worked around by comparing a canonical projection |
| **D12** | medium | Source inventory overcounted ~30% | a walk skipping only `__pycache__`/`.venv`/`.git`/`node_modules` counts `build/` — 205 duplicated files across 6 packages | fixed; 101,110 → 71,045 LOC |
| **D13** | medium | 21% of a corpus would be discarded by its own schema | `method-primitive-schema` declares 5 statuses; the corpus uses 8 (`OBSERVED` 7, `PAUSE` 1, `MEASURED` 1) | ingested and tagged rather than dropped |
| **D14** | medium | Declared ids collide where the schema says dedupe | 3 ids reused across cards; a node scheme keyed on declared id collapses them silently | node ids keyed on path; collisions reported |
| **D15** | low | Two test counts disagree on every package | README badges count pytest *cases*, `def test_` counts *functions* — 80/107, 53/56, 25/29 | both valid; name the measure per column |

**X1 is the framework's most defensible finding, and it got stronger.** The same failure shape has
now appeared independently in **four** unrelated codebases (X1, X1c, X1d and the original pair).
Anything that can fall back should either raise or record that it fell back — and a check whose
failure mode is silence is the same defect wearing a different hat.

**A second class is now visible: `[TYPED-NOT-EXTRACTED]`.** D12 and D15 are the same shape — a
number a human typed into a document, which a script could have derived. Both were wrong. Both were
caught only when something regenerated them. A number in a document is a claim with no gate on it.

---

## §9 · Anti-patterns — reject on sight

| Anti-pattern | Why |
|---|---|
| `UNIQUE(type, name)` on a table whose `id` derives from `(type,name)` | PK fires first; `ON CONFLICT` never triggers. Crashes only after an entity appears twice (L1.0) |
| Config 1 weights on a hash embedder | recall → 15% |
| Shipping on a builder-authored golden eval alone | measures memorization (§4) |
| `kg_augmented` on a dense graph | flat-score flooding (D2) |
| Silent fallback on retrieval failure | X1 — the cross-project class |
| Re-running `init --overwrite` over hand-edited `kg.py`/`asks.py` | destroys the edits |
| Importing another corpus's playbook results | 6 of 9 degraded across scales |
| Changing two variables and reporting a delta | attribution is gone (§6) |
| `PRAGMA foreign_keys = ON` with no `FOREIGN KEY` declared | enforces nothing; presence read as protection (X1c) |
| Skipping a bad reference without reporting it | X1 class — silence is not a pass (X1d) |
| Recursive graph traversal in a defect checker | fails loudest on the graphs most likely to be defective (D10) |
| Keying node ids on a declared id that is not unique | duplicates collapse without a message (D14) |
| Counting source files without excluding `build/`/`dist/` | inflates every derived total (D12) |
| Enforcing a schema's enum against a corpus that outgrew it | discards real content to defend a stale declaration (D13) |
| Typing a number into a document a script could extract | no gate; wrong until someone re-reads it by hand ([TYPED-NOT-EXTRACTED]) |
| Wall-clock timestamps in rows you intend to byte-compare | determinism lost at the storage layer (D11) |
| Reporting `|Δ| < 0.02` as an improvement | inside judge variance |
| Adding or reordering dimensions without re-indexing | every existing `.npz` is invalidated |
| Deleting a resolved defect from the record | it gets rebuilt |
| Named-attribute embeddings for open-domain or cross-language search at scale | wrong tool — use neural (`SPECS.ngf.md` §5) |
