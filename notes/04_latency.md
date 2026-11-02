# Latency

Latency is **wall-clock time** users wait. For LLM products you usually care about two numbers:

- **E2E** — request in → full answer out
- **TTFT (time to first token)** — request in → first streamed token (perceived snappiness)

Streaming does **not** make total generation faster; it improves TTFT perception.

## Stage breakdown (RAG)

Typical path and what dominates:

```text
cache → embed → retrieve → generate
  ms     tens–hundreds ms    usually largest
```

Instrument **each stage** with histograms so Prometheus can compute p50/p95 per stage. This lab returns timings in JSON and headers:

- JSON: `timings.embed_ms`, `retrieve_ms`, `llm_ttft_ms`, `llm_total_ms`, `e2e_ms`
- Headers: `X-E2E-Ms`, `X-TTFT-Ms`

Code: [`app/rag/pipeline.py`](../app/rag/pipeline.py), [`app/rag/generate.py`](../app/rag/generate.py) (streaming completion for real TTFT).

## Levers that actually move latency

1. **Cache hits** — skip embed + retrieve + generate entirely (biggest win on duplicates / paraphrases).
2. **Smaller context** — fewer / shorter chunks → fewer prompt tokens → faster generate.
3. **Faster / smaller models** — trade quality; validate with evals.
4. **Parallelism** — less common in single-query RAG; more relevant for multi-tool agents.

## Tradeoffs

| Change | Latency | Risk |
|--------|---------|------|
| Lower semantic cache threshold | ↓ | Wrong-answer hits ↑ (faithfulness ↓) |
| Raise `TOP_K` / chunk size | ↑ | Sometimes Hit@k ↑ |
| Broken creative prompt | ≈ same | Faithfulness ↓ |

Always pair latency experiments with evals. Faster and wrong is not a win.

## Bench script

```bash
python scripts/bench.py --rounds 2
```

Prints mean / p50 / p95 for cache off vs on over a fixed question list. Use it to prove the cache path is doing real work.
