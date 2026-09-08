# Repository guidance

## Orientation

This repository formalizes the KG-RAG framework and builds a graph of the related
repositories. It does not yet contain the proposed unified NLKE monorepo.

Read `declarations-clarification-correction.md`, then `MANIFEST.ngf.md` and
`BOOT.ngf.md`. Follow the boot sequence, including `SPECS.ngf.md` sections 3–4
and `COOKBOOK.ngf.md` section 9. Before design advice, query the local
`kg-tooling-expert` CLI as BOOT specifies; cite returned document IDs and paths,
or report unavailable or irrelevant retrieval honestly.

## Files and commands

- `TS-kg-rag-of-kg-rag.py`: graph builder, document renderers, and validation gate.
- `sources.json`: explicit source allowlist; do not replace it with broad discovery.
- `curated/`: authored findings, nodes, and doctrine mappings with source evidence.
- `TS-kg-rag-of-kg-rag.db`: generated graph.
- `TS-kg-rag-of-kg-rag.md` and `NLKE-production-quality-release-V1.0.0.md`:
  generated documents; change their inputs or renderer, not their output directly.
- The five `*.ngf.md` framework documents are authored, with checked body hashes.

Run commands from this directory with `python3 TS-kg-rag-of-kg-rag.py <command>`.
For changes affecting graph inputs, generated documents, or authored cards, the
documented sequence is `build` → `render` → `release` → `stamp` → `check`.
`stats` reads graph counts. Source repositories and the graph engine are external
dependencies resolved through `sources.json`; report missing dependencies.

`check` rebuilds into temporary storage and compares canonical database dumps,
checks positive assertions, document anchors and freshness, and authored-card
hashes. Passing this gate does not establish retrieval quality or NLKE release
readiness. An instructions-only edit needs review, not a graph regeneration.

## Evidence and engineering conventions

- A declaration pairs a falsifiable requirement with a named checking mechanism,
  enforcement level, and failure consequence. Unimplemented checks are gaps.
- Author judgments upstream, freeze their checking rules deliberately, and avoid
  inference at deterministic check time. An unavailable check reports `vacuous`,
  never `pass`.
- Preserve provenance, honest uncertainty, and resolved defect history. Label
  findings `OBSERVED`, `DIRECTIONAL`, or `NOT_ESTABLISHED` as appropriate.
- Report metrics with corpus scale, sample size, and judge. Builder-authored
  golden evaluations establish regression behavior, not general retrieval quality.
- Declare retrieval explicitly; follow the documented warnings about
  `kg_augmented`, embedding-class/weight mismatch, and dimension reindexing.
- Fix defects at their source and carry regression protection into generators.
  Never overwrite hand-edited generated agents without inspecting the diff.
- Keep deterministic data free of wall-clock noise. Do not silently skip invalid
  references or turn retrieval failures into successful empty results.
- Treat release specifications as proposed contracts until implementation and
  verification establish their claims. Reading a proposal does not authorize it.

<!-- in-the-loop:codex-team:begin -->
## In the Loop native Codex team

Repository-local `AGENTS.md`, `.codex/config.toml`, skills, permissions, and explicit user instructions remain authoritative.

- Use `sprinter` only when exact targets, a concrete reversible change, and named validation are all provided.
- Use `analyst` for clear, read-heavy extraction or review; use `operator` for integrated implementation and verification.
- Use `architect` for material ambiguity, architecture, security, or repeated failure. Use the requested `planner` (documented `gpt-5.6-sol`, `xhigh`) for an isolated, closed-context plan.
- The core four inherit the session model; built-in `default`, `worker`, and `explorer` remain valid fallbacks.
- Parent retains user questions, approvals, graph control, waiting, and consolidation. Retry a role once only for malformed or transient output, then route or escalate.
- Any resumed session, goal, checkpoint, conversation, or repository-state recovery is read-only until the parent obtains fresh, active-session approval for the exact protected effect and target. A bare `continue` or `resume` is not that approval.

Every delegation includes `objective:`, `context_and_inputs:`, `scope:`, `constraints:`, `authority:`, `deliverable:`, `acceptance_evidence:`, `budget:`, and `escalate_when:`.

Every result includes `status: complete | partial | blocked`, `summary:`, `evidence:`, `artifacts_or_changed_files:`, `verification:`, `risks_or_unknowns:`, and `recommended_next_route:`.

Context does not grant authority. Treat dispatch and model output as claims until independently observed through tests, state, screenshots, receipts, or equivalent evidence.
<!-- in-the-loop:codex-team:end -->
