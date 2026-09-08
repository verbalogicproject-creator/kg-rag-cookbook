# NLKE Hybrid operations

Install the package with its declared local dependency:

```bash
python3 -m pip install -e /root/projects/declared_core
python3 -m pip install -e .
```

Run `nlke-hybrid doctor` before indexing. It observes the local embedding,
reranker, and generator services without restarting them, verifies the canonical
`declared_core` revision and digest, and reports the configured 1,024-token
embedding and 4,096-token generation contexts.

```bash
nlke-hybrid index --providers local
nlke-hybrid search "declared core RRF fusion" --mode local
nlke-hybrid ask "How is graph expansion bounded?" --mode local
nlke-hybrid index --providers both
nlke-hybrid search "declared core RRF fusion" --mode cloud
nlke-hybrid search "declared core RRF fusion" --mode both
nlke-hybrid status
```

`index --providers both` never sends cloud-ineligible sources, including the
user-supplied deterministic KG-RAG example, to Gemini. It resumes only chunks
without a matching profile identity. If Gemini returns a rate limit or another
transient error, already committed vectors remain visible, the job is
`incomplete`, and a later index command resumes from coverage rather than
overwriting vectors.

For quality qualification, provide a frozen JSON query set:

```json
{
  "judge": "independent reviewer",
  "queries": [
    {
      "query": "Which component implements RRF?",
      "relevant_ids": ["chunk:<stable id>"],
      "independent": true
    }
  ]
}
```

Then run `nlke-hybrid evaluate blind-queries.json`. The report measures lexical,
local, cloud, and combined retrieval and supports graph/reranker ablations. It
returns `NOT_ESTABLISHED` unless there are at least 20 independently authored
blind queries; builder regression cases must remain separate.
