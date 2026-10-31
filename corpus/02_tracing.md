# Tracing LLM Applications

Tracing records the path of a single request through every stage of your pipeline. Unlike logs, traces nest spans so you can see parent-child timing and payloads.

## What to capture

For a RAG request, create one root trace and child spans for:
- cache lookup
- query embedding
- vector retrieval
- LLM generation

Attach inputs, outputs, retrieved chunk ids, token counts, model name, and prompt version as metadata.

## Debugging with traces

If answers are wrong, open the trace and check retrieval first: empty or irrelevant chunks explain most failures. If chunks look right but the answer invents facts, the generation prompt or model is the problem. Errored spans surface timeouts and API failures without digging through raw logs.

## Correlation

Propagate a request id from the HTTP layer into every span. That lets you jump from a Grafana latency spike to the exact Langfuse trace for that request.
