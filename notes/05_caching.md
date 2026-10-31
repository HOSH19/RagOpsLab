# Caching

Caching avoids repeating expensive work. In RAG the expensive path is **embed → retrieve → generate**. A good cache cuts latency, tokens, and cost — if you version keys and watch quality.

## Exact cache

**Key:** hash of `normalized_query | model | prompt_version`  
**Hit:** identical (normalized) question under the same model and prompt → return stored answer.

Normalization usually means lowercase + collapse whitespace so `"What is TTFT?"` and `"what is ttft?"` share a key.

**Why prompt version is in the key:** if you change the system prompt but reuse old cached answers, users silently get policy from `v0` while you think you shipped `v1`.

Code: [`app/cache/exact.py`](../app/cache/exact.py)

## Semantic cache

**Idea:** embed the query; if cosine similarity to a previously cached query ≥ threshold (lab default **0.92**), reuse that answer.

| Threshold | Effect |
|-----------|--------|
| Higher (e.g. 0.95) | Fewer hits, safer |
| Lower (e.g. 0.85) | More hits, more wrong-question reuse |

Always re-run faithfulness evals after changing `SEMANTIC_CACHE_THRESHOLD`.

Code: [`app/cache/semantic.py`](../app/cache/semantic.py)

## Response shape in this lab

- Body field `cache`: `HIT` | `SEMANTIC` | `MISS`
- Header `X-Cache`: same
- Metrics: `cache_hits_total{type=...}`, `cache_lookups_total{type=...}`

Force a miss:

```bash
curl -s localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is TTFT?","use_cache":false}'
```

## TTLs

Set a TTL (lab: `CACHE_TTL_SECONDS`). Unbounded caches serve outdated facts long after the corpus or product rules changed. Exact keys already version by prompt/model; TTL covers content drift.

## Failure modes

- **Semantic false friends** — similar wording, different intent (“cancel subscription” vs “cancel order”).
- **Redis down** — this lab soft-fails cache and still serves RAG (with a warning log).
- **Cache poisoning** — bad first answer gets stored and replayed; fix by version bump, TTL, or deleting keys after bad deploys.

## Experiment

1. Ask a question twice → expect `MISS` then `HIT`, huge e2e drop.
2. Ask a close paraphrase → often `SEMANTIC`.
3. Lower threshold → more semantic hits → re-run evals and watch faithfulness.
