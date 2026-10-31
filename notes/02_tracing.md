# Tracing

Tracing records **one request’s path** through the pipeline: what ran, in what order, with what inputs/outputs, and how long each step took. Logs are lines; traces are nested trees of **spans**.

## Why LLM apps need traces

Failures are ambiguous without structure:

- Wrong answer because **retrieval** returned junk?
- Or chunks were fine but the **prompt/model** hallucinated?
- Or **cache** served a stale/wrong semantic hit?

A single Langfuse trace with child spans makes that visible in one UI click.

## Spans in this lab

Each `/ask` creates a root trace (`rag_ask`) with children:

| Span | What it captures |
|------|------------------|
| `cache_lookup` | HIT / SEMANTIC / MISS (and similarity when relevant) |
| `embed` | Query embedding |
| `retrieve` | Top-k chunk ids + doc ids |
| `generate` | Answer + TTFT / total LLM time |
| generation record | Model, tokens, prompt version |

Implementation: [`app/observability/tracing.py`](../app/observability/tracing.py), called from [`app/rag/pipeline.py`](../app/rag/pipeline.py).

## Metadata that matters

Attach enough to debug without drowning:

- `request_id` — join traces to HTTP headers / Grafana spikes
- `prompt_version` — attribute quality changes after prompt edits
- `model`, token usage
- retrieved `doc_ids` / `chunk_ids`
- cache outcome

## Tracing vs monitoring vs evals

| Tool | Question it answers |
|------|---------------------|
| **Trace** | What happened on *this* request? |
| **Monitor** | Is the *fleet* healthy right now? |
| **Eval** | Is quality *good enough* on a fixed set? |

Use monitors to find a latency/error spike → open a few traces → confirm whether retrieval or generation broke → add a golden case and lock it with an eval.

## Practical tips

- Propagate one id from the HTTP layer into every span (this lab uses `X-Request-Id` / `request_id`).
- Prefer structured inputs/outputs on spans over dumping entire prompts into unstructured logs.
- Mark errors on the failing span (`level=ERROR`) so the UI highlights broken stages.
