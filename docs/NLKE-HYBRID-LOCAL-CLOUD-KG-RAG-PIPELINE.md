# NLKE Hybrid Local–Cloud KG-RAG Pipeline

## Status

`[IMPLEMENTATION CONTRACT]` This document records the approved V1 plan that
the `nlke_hybrid` package implements. It is a contract until the named checks
run; it does not claim retrieval quality in advance of evaluation.

## Scope

V1 indexes declared code and documentation sources, optionally adds Gemini
embeddings for cloud-eligible content, reads the estate graph without mutating
it, and uses a local Qwen-compatible service only for optional answer
generation. It provides local, cloud, and explicitly selected combined search.

The package does not modify sibling repositories or model-server settings. It
does not implement multimodal retrieval, cloud generation, automatic memory
writes, a web UI, or a monorepo migration.

## Declared contracts

| ID | Requirement | Checker | Level | Failure consequence |
| --- | --- | --- | --- | --- |
| NLKE-01 | Configuration, sources, profiles, and paths are valid | `nlke-hybrid check` | lint | refuse operation |
| NLKE-02 | Embeddings match their provider identity and 768 dimensions | provider/store tests | gate | reject vector |
| NLKE-03 | Source changes are atomic and coverage is per profile | store/index tests | gate | incomplete receipt |
| NLKE-04 | Local mode makes no Gemini request | provider tests | gate | test failure |
| NLKE-05 | Graph traversal has a one-hop and result cap | graph/retrieval tests | gate | test failure |
| NLKE-06 | Answers cite only supplied passage IDs | generation tests | gate | refuse answer |
| NLKE-07 | Independent quality evidence has 20 blind queries | `evaluate` input | review | qualification remains incomplete |

`evaluate` reports a missing independent blind set as `NOT_ESTABLISHED`; it
never turns builder-authored regression cases into quality evidence.

## Retrieval declaration

The sequence is exact identifier/path resolution and BM25 plus selected dense
profiles, bounded declared-edge expansion, weighted RRF (`k=60`), local BGE
reranking, cited context, then optional local generation. Initial weights are
lexical `1`, graph `0.5`, semantic `1`; `both` divides semantic weight across
the two dense profiles. Default mode is `local`.

Each source, chunk, relation, embedding profile, vector, signal contribution,
and degradation is stored separately. The graph database is opened read-only.
The declared source set begins with this repository and the user-supplied
deterministic KG-RAG case study. The latter is cloud-ineligible by declaration.

## Release evidence boundary

V1 is installable when structural contract tests and CLI checks pass and both
provider adapters have been exercised with their configured services. Its
retrieval quality is qualified only after a frozen corpus and at least twenty
independently authored blind queries measure lexical-only, local, cloud, and
combined modes with graph and reranker ablations. Required reports include
Recall@5/10, MRR@10, nDCG@10, citation validity, p50/p95 latency, coverage,
storage, cloud token usage, corpus size, sample size, judges, and model
configuration. Cloud or combined mode cannot become the default absent
measured benefit.
