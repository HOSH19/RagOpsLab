from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.config import get_settings
from app.observability.metrics import APP_INFO
from app.rag.ingest import ingest_corpus
from app.rag.pipeline import RagPipeline

pipeline: RagPipeline | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pipeline
    settings = get_settings()
    APP_INFO.info(
        {
            "prompt_version": settings.prompt_version,
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
        }
    )
    pipeline = RagPipeline(settings)
    yield


app = FastAPI(title="AI Engineering Lab — RAG Ops", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    use_cache: bool | None = Field(
        default=None,
        description="Omit or true to use cache; false forces a full RAG miss (no read/write).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"question": "What is TTFT?"},
                {"question": "What commonly drives haze in Singapore?"},
            ]
        }
    }


class TimingsModel(BaseModel):
    cache_ms: float
    embed_ms: float
    retrieve_ms: float
    llm_ttft_ms: float
    llm_total_ms: float
    e2e_ms: float


class AskResponse(BaseModel):
    answer: str
    cache: str
    cache_enabled: bool
    doc_ids: list[str]
    chunk_ids: list[str]
    timings: TimingsModel
    prompt_tokens: int
    completion_tokens: int
    model: str
    prompt_version: str
    request_id: str
    semantic_similarity: float | None = None


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    response: Response,
    x_use_cache: str | None = Header(default=None),
) -> AskResponse:
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not ready")
    use_cache = body.use_cache
    if x_use_cache is not None:
        use_cache = x_use_cache.lower() in {"1", "true", "yes"}
    try:
        result = pipeline.ask(body.question, use_cache=use_cache)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response.headers["X-Cache"] = result.cache
    response.headers["X-Request-Id"] = result.request_id
    response.headers["X-E2E-Ms"] = f"{result.timings.e2e_ms:.2f}"
    response.headers["X-TTFT-Ms"] = f"{result.timings.llm_ttft_ms:.2f}"

    return AskResponse(
        answer=result.answer,
        cache=result.cache,
        cache_enabled=result.cache_enabled,
        doc_ids=result.doc_ids,
        chunk_ids=result.chunk_ids,
        timings=TimingsModel(**result.timings.__dict__),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        model=result.model,
        prompt_version=result.prompt_version,
        request_id=result.request_id,
        semantic_similarity=result.semantic_similarity,
    )


@app.post("/ingest")
def ingest(reset: bool = Query(default=True)) -> dict[str, Any]:
    try:
        return ingest_corpus(reset=reset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class EvalScoresPayload(BaseModel):
    scores: dict[str, float]


@app.post("/evals/scores")
def push_eval_scores(body: EvalScoresPayload) -> dict[str, str]:
    from app.observability.metrics import set_eval_score

    for name, value in body.scores.items():
        set_eval_score(name, float(value))
    return {"status": "ok", "updated": str(len(body.scores))}


@app.get("/metrics")
def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
