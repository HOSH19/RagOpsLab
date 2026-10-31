# AI Engineering Lab — RAG Ops

A hands-on local lab for **evals**, **tracing**, **monitoring**, **latency**, and **caching** on a real RAG Q&A service.

```text
curl → FastAPI /ask → Redis cache → Chroma retrieve → LLM generate
                 ↘ Langfuse traces          ↘ Prometheus → Grafana
```

## Quick start

### 1. Infra

```bash
cd ai-eng-lab
docker compose up -d
```

| Service    | URL                         | Notes                          |
|------------|-----------------------------|--------------------------------|
| Langfuse   | http://localhost:3000       | Create a project + API keys    |
| Grafana    | http://localhost:3001       | admin / admin                  |
| Prometheus | http://localhost:9090       | Scrapes host `:8000/metrics`   |
| Redis      | localhost:6379              | Exact + semantic cache         |

In Langfuse (first visit): create an account → project → **Settings → API Keys**. Copy public/secret keys into `.env`. The lab pins **Langfuse Python SDK v2** to match `langfuse/langfuse:2` in Compose.

### 2. App

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# set OPENAI_API_KEY (or point OPENAI_BASE_URL at your vLLM)
# set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY from the UI

export PYTHONPATH=.
python -m app.rag.ingest          # embed corpus → ./data/chroma
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Ask a question

```bash
curl -s http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is TTFT?"}' | jq
```

Response includes `cache` (`HIT` | `SEMANTIC` | `MISS`), `timings` (embed / retrieve / TTFT / e2e), and `doc_ids`. Headers: `X-Cache`, `X-E2E-Ms`, `X-TTFT-Ms`.

Open the matching trace in Langfuse (spans: `cache_lookup`, `embed`, `retrieve`, `generate`).

---

## Learning path

### Caching

Exact cache keys: `sha256(normalized_query | model | prompt_version)`.  
Semantic cache: cosine similarity ≥ `SEMANTIC_CACHE_THRESHOLD` (default `0.92`).

**Experiment:** ask the same question twice → second should be `HIT` with ~ms e2e. Ask a paraphrase → often `SEMANTIC`. Lower threshold to `0.85`, re-run evals, watch faithfulness drop.

```bash
# force miss
curl -s http://localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is TTFT?","use_cache":false}' | jq '.cache,.timings'
```

### Latency

Stage histograms: `embed`, `retrieve`, `llm_ttft`, `llm_total`, `e2e` (Prometheus + JSON `timings`). Generation streams so TTFT is real.

```bash
python scripts/bench.py --rounds 2
```

Compare p50/p95 with cache on vs off.

### Tracing

Every `/ask` creates a Langfuse root trace with child spans and a generation record (tokens, prompt version, retrieved ids). Failures mark errored pipeline paths.

**Experiment:** break retrieval (set `TOP_K=0` temporarily) and inspect the trace — generation still runs but context is empty.

### Monitoring

- App: `http://localhost:8000/metrics`
- Grafana dashboard **RAG Ops Lab**: e2e latency, stage p95, cache hit ratio, tokens, errors, latest eval gauges

**Experiment:** flood asks (`bench.py`) and watch Grafana panels move.

### Evals

Golden set: [`evals/datasets/golden.jsonl`](evals/datasets/golden.jsonl) (~30 Qs with `expected_doc_ids` + reference answers).

```bash
# retrieval + keyword overlap + LLM-as-judge (faithfulness / relevance)
python -m evals.run_evals --no-cache --output data/eval_report.json

# faster: skip judge
python -m evals.run_evals --no-cache --no-judge --limit 10
```

Metrics: Hit@k, MRR, keyword overlap, judge means. Scores are written to the report, pushed to Langfuse when configured, and POSTed to `http://localhost:8000/evals/scores` so Grafana can scrape `rag_eval_score` from the API.

**Regression workflow**

1. Run evals on `PROMPT_VERSION=rag-answer-v1`, save report.
2. Set `PROMPT_VERSION=rag-answer-v0-broken` and restart.
3. Re-run evals — faithfulness should collapse while latency stays similar.
4. Diff reports / Langfuse scores before shipping prompt changes.

---

## Corpus

Markdown under [`corpus/`](corpus/): AI-eng notes (evals, tracing, monitoring, latency, caching, RAG, prompts, tokens) plus Singapore haze planner notes for a familiar second domain.

Re-ingest after edits:

```bash
python -m app.rag.ingest
# or POST http://localhost:8000/ingest
```

## Config

See [`.env.example`](.env.example). Important knobs:

| Variable | Role |
|----------|------|
| `OPENAI_BASE_URL` | OpenAI or local vLLM |
| `PROMPT_VERSION` | Prompt + cache key version (`rag-answer-v1` / `rag-answer-v0-broken`) |
| `SEMANTIC_CACHE_THRESHOLD` | Semantic hit aggressiveness |
| `CHUNK_SIZE` / `TOP_K` | Retrieval shape → Hit@k tradeoffs |
| `LANGFUSE_*` | Tracing / scores |

## Project layout

```text
app/main.py              FastAPI /ask /health /metrics /ingest
app/rag/                 ingest, retrieve, generate, pipeline
app/cache/               exact + semantic Redis
app/observability/       Langfuse + Prometheus
evals/                   golden set, judges, runner
corpus/                  source docs
grafana/ dashboards      RAG Ops Lab
scripts/bench.py         cache on/off latency comparison
```

## Success checklist

- [ ] `/ask` returns an answer grounded in corpus docs
- [ ] Langfuse shows nested spans for a request
- [ ] Second identical ask is `X-Cache: HIT`
- [ ] Grafana shows e2e latency and cache hit ratio
- [ ] `python -m evals.run_evals --no-cache` prints Hit@k / MRR / judge means
