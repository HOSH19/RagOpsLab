from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

REQUESTS = Counter(
    "rag_requests_total",
    "Total /ask requests",
    ["cache", "status"],
)

ERRORS = Counter(
    "rag_errors_total",
    "Total errors",
    ["stage"],
)

CACHE_HITS = Counter(
    "cache_hits_total",
    "Cache hits by type",
    ["type"],
)

CACHE_LOOKUPS = Counter(
    "cache_lookups_total",
    "Cache lookups",
    ["type"],
)

STAGE_LATENCY = Histogram(
    "rag_stage_latency_seconds",
    "Latency by pipeline stage",
    ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

E2E_LATENCY = Histogram(
    "rag_e2e_latency_seconds",
    "End-to-end /ask latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

TOKENS = Counter(
    "rag_tokens_total",
    "LLM tokens",
    ["type"],
)

EVAL_SCORE = Gauge(
    "rag_eval_score",
    "Latest offline eval score",
    ["metric"],
)

APP_INFO = Info("rag_app", "RAG lab app info")


def observe_stage(stage: str, seconds: float) -> None:
    STAGE_LATENCY.labels(stage=stage).observe(seconds)


def observe_e2e(seconds: float) -> None:
    E2E_LATENCY.observe(seconds)


def record_request(cache: str, status: str = "ok") -> None:
    REQUESTS.labels(cache=cache, status=status).inc()


def record_cache(lookup_type: str, hit: bool) -> None:
    CACHE_LOOKUPS.labels(type=lookup_type).inc()
    if hit:
        CACHE_HITS.labels(type=lookup_type).inc()


def record_tokens(prompt: int, completion: int) -> None:
    if prompt:
        TOKENS.labels(type="prompt").inc(prompt)
    if completion:
        TOKENS.labels(type="completion").inc(completion)


def record_error(stage: str) -> None:
    ERRORS.labels(stage=stage).inc()


def set_eval_score(metric: str, value: float) -> None:
    EVAL_SCORE.labels(metric=metric).set(value)
