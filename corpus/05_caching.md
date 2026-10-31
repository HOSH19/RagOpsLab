# Caching for LLM Apps

Caching avoids repeating expensive work. In RAG, the expensive path is embed → retrieve → generate.

## Exact cache

Hash the normalized query together with model id and prompt version. On an exact match, return the stored answer. Invalidate or version keys when prompts or models change so users never get stale policy text.

## Semantic cache

Embed the query and compare against embeddings of previously cached queries. If cosine similarity exceeds a threshold (commonly around 0.90–0.95), reuse the prior answer. Lower thresholds increase hit rate and wrong-answer risk.

## What to measure

Log `HIT`, `SEMANTIC`, or `MISS` on every request. Track hit ratio and the latency delta between hits and misses. Pair cache experiments with eval scores so quality regressions are visible.

## TTLs

Set a TTL on cache entries. Product facts change; unbounded caches quietly serve outdated answers.
