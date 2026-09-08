# NLKE Hybrid local release report

## Structural evidence

`[OBSERVED]` The package built into `nlke_hybrid-0.1.0-py3-none-any.whl` and
installed in a clean temporary environment with the canonical
`declared-core` editable dependency. The canonical dependency verification
observed revision `526961e9edbc07f21db39d2183fc0ddc74066dbd` and tree digest
`c9e1bad0e3d06a6a428ef5d76fb6d2ddcccc287d01f8eff71f68102fa36118c4`.

`[OBSERVED]` Six contract tests passed. They cover malformed-vector rejection,
local request formatting and response-order handling, Gemini task formatting,
local-mode cloud isolation, profile separation, one-hop graph behavior, and
citation resolution with a deterministic generator.

`[OBSERVED]` `doctor` verified the live local services without restarting them:
EmbeddingGemma Q8 (768 dimensions, 1,024 context), BGE reranker Q8 (2,048
context), and Qwen 2.5 Q4 (4,096 context). The configured profile identities
were corrected from an initial Q4 assumption after this observation; the local
index was rebuilt under the Q8 identity.

## Runtime evidence

`[OBSERVED]` The declared estate graph imported read-only as 1,260 nodes and
1,298 edges. The local Q8 embedding profile completed for the indexed corpus.
Local search returned receipted source IDs, content hashes, locations, and
lexical/local-semantic signal contributions. A direct Qwen-compatible
completion smoke request returned an OpenAI-shaped completion with `[P001]`.

`[OBSERVED, PARTIAL]` Gemini `gemini-embedding-001` accepted the declared
`RETRIEVAL_DOCUMENT`, `RETRIEVAL_QUERY`, and `CODE_RETRIEVAL_QUERY` adapter
contract and persisted cloud vectors. Its full index did not complete because
the configured account returned `429 RESOURCE_EXHAUSTED` after 90 current
eligible chunks. The job remains explicitly `incomplete` and resumable; no
cloud profile is labelled complete.

## Qualification

`[NOT_ESTABLISHED]` Retrieval quality is not qualified. No frozen evaluation
contains the required 20 independently authored blind queries, so Recall@5/10,
MRR@10, nDCG@10, citation validity, p50/p95 latency, and comparative ablations
are intentionally unreported. The cloud and combined modes remain opt-in;
local remains the default.
