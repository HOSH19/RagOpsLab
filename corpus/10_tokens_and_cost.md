# Tokens and Cost

LLM cost scales with tokens. Prompt tokens include the system prompt, retrieved chunks, and user question. Completion tokens are the generated answer.

## Monitoring spend

Export token counters to Prometheus. Track prompt tokens, completion tokens, and estimated USD if you know unit prices. Cache hits should show zero new LLM tokens for that request.

## Controlling cost

- Retrieve fewer chunks or shorter chunks
- Cap max generation tokens
- Cache exact and semantic duplicates
- Prefer smaller models for classification-style substeps; reserve larger models for final answers

## Latency link

More prompt tokens usually mean higher generation latency. Cost and latency optimizations often move together when you shrink context.
