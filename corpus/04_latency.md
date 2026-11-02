# Latency in LLM Pipelines

End-to-end (e2e) latency is the wall-clock time from request receipt to full response. For streaming APIs, TTFT (time to first token) often matters more for perceived speed.

## Stage breakdown

Typical RAG stages and what dominates them:
- embed: embedding API call for the query
- retrieve: vector search over the index
- generate: LLM completion (usually the largest share)

Instrument each stage with histograms, not just timers printed once. Histograms let Prometheus compute p50/p95.

## Improving latency

Caching repeated or near-duplicate queries removes embed+retrieve+generate entirely on hits. Smaller context (fewer chunks, shorter chunks) reduces prompt tokens and generation time. Streaming does not reduce total time but improves TTFT perception.

## Tradeoffs

Aggressive semantic cache thresholds cut latency but can return answers for the wrong question. Always re-run faithfulness evals after changing cache similarity.
