# Monitoring AI Systems

Monitoring watches live traffic health. Evals prove quality offline; monitoring proves the system stays healthy under load.

## Core metrics

Track request rate, error rate, and latency percentiles (p50, p95, p99). For LLMs also track:
- tokens per request (prompt + completion)
- cache hit ratio
- TTFT (time to first token) for streaming

## Alerting

Alert on error rate and p95 latency, not only averages. Averages hide tail latency that users feel. Cache hit ratio crashes often mean Redis is down or keys are versioned incorrectly after a prompt change.

## Dashboards

A useful RAG dashboard shows e2e latency, stage breakdowns (embed / retrieve / generate), cache hits by type (exact vs semantic), token spend, and recent error counts. Pair Grafana with traces so an alert links to examples.
