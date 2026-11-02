# RAG (Retrieval-Augmented Generation)

RAG grounds an LLM on **your documents** so answers can cite and stay faithful to a corpus instead of relying only on model memory.

## Pipeline

```text
1. Ingest   chunk docs → embed → store vectors (Chroma)
2. Retrieve embed query → top-k similar chunks
3. Generate prompt(system + context + question) → answer
```

In this lab:

- Ingest: `python -m app.rag.ingest` or `POST /ingest`
- Retrieve / generate: wired in [`app/rag/pipeline.py`](../app/rag/pipeline.py)
- Corpus: [`corpus/`](../corpus/) (AI-eng notes + haze product notes)

## Chunking

| Choice | Upside | Downside |
|--------|--------|----------|
| Small chunks | Precise matches | Lose surrounding context |
| Large chunks | More context | Diluted similarity, more tokens |
| Overlap | Fewer boundary misses | Duplicate text in index |

Knobs: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K` in `.env`.

## Failure modes

1. **Retrieval miss** — answer exists in corpus but wasn’t retrieved → fix chunking / embeddings / k / indexing.
2. **Hallucination** — right chunks, invented claims → fix prompt, require grounding, stronger model.
3. **Out of scope** — nothing relevant → system should refuse (lab system prompt: answer only from context).

Evals separate (1) vs (2): Hit@k vs faithfulness.

## Prompt versioning

Treat prompts like code. This lab uses `PROMPT_VERSION` (`rag-answer-v1` vs broken `rag-answer-v0-broken`) in:

- the system prompt selection
- exact/semantic cache keys
- Langfuse trace metadata
- eval reports

Bump the version on any wording change that could change behavior.

## Tokens and cost

Prompt tokens ≈ system + retrieved chunks + question. Completion tokens ≈ answer length. Caching and tighter retrieval cut both cost and latency. See corpus doc `10_tokens_and_cost.md` and Prometheus `rag_tokens_total`.

## How RAG ties the other pillars together

- **Evals** measure retrieval + answer quality on a golden set  
- **Tracing** shows which chunks fed a bad answer  
- **Monitoring** watches live latency, errors, cache, tokens  
- **Latency** is dominated by generate unless cache hits  
- **Caching** short-circuits the whole RAG path when safe  
