# Monitoring

Monitoring watches **live traffic health**: rates, errors, latency percentiles, cache efficiency, token spend. Evals prove quality offline; monitoring proves the system stays healthy under load.

## Core signals for RAG / LLM APIs

| Signal | Why |
|--------|-----|
| Request rate | Load / traffic shape |
| Error rate by stage | embed vs retrieve vs generate failures |
| Latency p50 / p95 / p99 | Users feel the tail, not the mean |
| Cache hit ratio | Cost + latency wins (or Redis/key bugs) |
| Tokens (prompt / completion) | Cost proxy |
| Eval score gauges | Latest offline quality snapshot |

## Percentiles over averages

Averages hide pain. One slow generate call can ruin p95 while the mean still looks fine. Always chart **histograms** and alert on **p95** (and error rate), not only mean latency.

## Stack in this lab

```text
/ask  →  Prometheus counters/histograms  →  Grafana dashboard
              ↑
         GET /metrics
```

- Metrics code: [`app/observability/metrics.py`](../app/observability/metrics.py)
- Scrape config: [`prometheus/prometheus.yml`](../prometheus/prometheus.yml) (targets `host.docker.internal:8000`)
- Dashboard: Grafana → **RAG Ops Lab** (e2e latency, stage p95, cache hits, tokens, errors, eval gauges)

## Useful metric names

- `rag_e2e_latency_seconds` — end-to-end histogram
- `rag_stage_latency_seconds{stage=...}` — embed / retrieve / llm_ttft / …
- `cache_hits_total{type=exact|semantic}` / `cache_lookups_total`
- `rag_requests_total{cache,status}`
- `rag_tokens_total{type=prompt|completion}`
- `rag_errors_total{stage=...}`
- `rag_eval_score{metric=...}` — pushed after `evals.run_evals` via `/evals/scores`

## Alerting mindset (conceptual)

- Error rate up → check generate/API keys/model endpoint
- p95 up, errors flat → model slow, context too large, or cache miss storm
- Cache hit ratio cliffs → Redis down, or `prompt_version` / model changed and invalidated keys (expected) vs bug

## Experiment

Run `python scripts/bench.py` while Grafana is open. Watch e2e latency and cache hit ratio move as the second pass hits exact cache.
