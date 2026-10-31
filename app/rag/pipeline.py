from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.cache.exact import CachedAnswer, ExactCache
from app.cache.semantic import SemanticCache
from app.config import Settings, get_settings
from app.llm import embed_query
from app.observability import metrics
from app.observability.tracing import TraceHandle, start_trace
from app.rag.generate import generate_answer
from app.rag.retrieve import RetrievedChunk, retrieve


@dataclass
class AskTimings:
    cache_ms: float = 0.0
    embed_ms: float = 0.0
    retrieve_ms: float = 0.0
    llm_ttft_ms: float = 0.0
    llm_total_ms: float = 0.0
    e2e_ms: float = 0.0


@dataclass
class AskResult:
    answer: str
    cache: str  # HIT | SEMANTIC | MISS
    doc_ids: list[str]
    chunk_ids: list[str]
    timings: AskTimings
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    prompt_version: str = ""
    request_id: str = ""
    semantic_similarity: float | None = None
    cache_enabled: bool = True
    chunks: list[RetrievedChunk] = field(default_factory=list)


class RagPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.exact = ExactCache(settings=self.settings)
        self.semantic = SemanticCache(settings=self.settings)

    def ask(self, question: str, use_cache: bool | None = None) -> AskResult:
        settings = self.settings
        cache_enabled = settings.cache_enabled if use_cache is None else use_cache
        e2e_start = time.perf_counter()
        timings = AskTimings()

        with start_trace(
            name="rag_ask",
            input_data={"question": question},
            metadata={
                "prompt_version": settings.prompt_version,
                "model": settings.chat_model,
                "cache_enabled": cache_enabled,
            },
        ) as trace:
            try:
                result = self._ask_inner(
                    question=question,
                    cache_enabled=cache_enabled,
                    timings=timings,
                    e2e_start=e2e_start,
                    trace=trace,
                )
                metrics.record_request(cache=result.cache, status="ok")
                metrics.observe_e2e(result.timings.e2e_ms / 1000.0)
                trace.update(
                    output={"answer": result.answer, "cache": result.cache},
                    metadata={
                        "doc_ids": result.doc_ids,
                        "chunk_ids": result.chunk_ids,
                        "timings": timings.__dict__,
                    },
                )
                return result
            except Exception as exc:
                metrics.record_error(stage="pipeline")
                metrics.record_request(cache="ERROR", status="error")
                trace.update(output={"error": str(exc)}, metadata={"error": True})
                raise

    def _ask_inner(
        self,
        question: str,
        cache_enabled: bool,
        timings: AskTimings,
        e2e_start: float,
        trace: TraceHandle,
    ) -> AskResult:
        settings = self.settings
        model = settings.chat_model
        prompt_version = settings.prompt_version

        # --- cache lookup ---
        cache_start = time.perf_counter()
        cache_span = trace.span("cache_lookup", input_data={"question": question})
        if cache_enabled:
            exact_hit = self.exact.get(question, model, prompt_version)
            metrics.record_cache("exact", hit=bool(exact_hit))
            if exact_hit:
                timings.cache_ms = (time.perf_counter() - cache_start) * 1000
                metrics.observe_stage("cache", timings.cache_ms / 1000.0)
                trace.end_span("cache_lookup", output={"result": "HIT"})
                timings.e2e_ms = (time.perf_counter() - e2e_start) * 1000
                return AskResult(
                    answer=exact_hit.answer,
                    cache="HIT",
                    doc_ids=exact_hit.doc_ids,
                    chunk_ids=exact_hit.chunk_ids,
                    timings=timings,
                    model=model,
                    prompt_version=prompt_version,
                    request_id=trace.request_id,
                    cache_enabled=cache_enabled,
                )
        else:
            trace.end_span("cache_lookup", output={"result": "DISABLED"})

        # Need embedding for semantic cache + retrieve
        embed_start = time.perf_counter()
        trace.span("embed", input_data={"question": question})
        try:
            query_embedding = embed_query(question)
        except Exception:
            metrics.record_error(stage="embed")
            raise
        timings.embed_ms = (time.perf_counter() - embed_start) * 1000
        metrics.observe_stage("embed", timings.embed_ms / 1000.0)
        trace.end_span("embed", output={"dims": len(query_embedding)})

        semantic_sim: float | None = None
        if cache_enabled:
            semantic_hit, semantic_sim = self.semantic.lookup(query_embedding, model, prompt_version)
            metrics.record_cache("semantic", hit=bool(semantic_hit))
            if semantic_hit:
                timings.cache_ms = (time.perf_counter() - cache_start) * 1000
                metrics.observe_stage("cache", timings.cache_ms / 1000.0)
                try:
                    cache_span.end(output={"result": "SEMANTIC", "similarity": semantic_sim})
                except Exception:
                    pass
                timings.e2e_ms = (time.perf_counter() - e2e_start) * 1000
                return AskResult(
                    answer=semantic_hit.answer,
                    cache="SEMANTIC",
                    doc_ids=semantic_hit.doc_ids,
                    chunk_ids=semantic_hit.chunk_ids,
                    timings=timings,
                    model=model,
                    prompt_version=prompt_version,
                    request_id=trace.request_id,
                    semantic_similarity=semantic_sim,
                    cache_enabled=cache_enabled,
                )
            try:
                cache_span.end(output={"result": "MISS", "best_similarity": semantic_sim})
            except Exception:
                pass
        timings.cache_ms = (time.perf_counter() - cache_start) * 1000
        metrics.observe_stage("cache", timings.cache_ms / 1000.0)

        # --- retrieve ---
        retrieve_start = time.perf_counter()
        trace.span("retrieve", input_data={"top_k": settings.top_k})
        try:
            chunks = retrieve(question, query_embedding=query_embedding, settings=settings)
        except Exception:
            metrics.record_error(stage="retrieve")
            raise
        timings.retrieve_ms = (time.perf_counter() - retrieve_start) * 1000
        metrics.observe_stage("retrieve", timings.retrieve_ms / 1000.0)
        doc_ids = list(dict.fromkeys(c.doc_id for c in chunks))
        chunk_ids = [c.chunk_id for c in chunks]
        trace.end_span(
            "retrieve",
            output={"chunk_ids": chunk_ids, "doc_ids": doc_ids},
        )

        # --- generate ---
        trace.span("generate", input_data={"prompt_version": prompt_version})
        try:
            gen = generate_answer(question, chunks, settings=settings, stream=True)
        except Exception:
            metrics.record_error(stage="generate")
            raise
        timings.llm_ttft_ms = gen.ttft_ms
        timings.llm_total_ms = gen.total_ms
        metrics.observe_stage("llm_ttft", gen.ttft_ms / 1000.0)
        metrics.observe_stage("llm_total", gen.total_ms / 1000.0)
        metrics.record_tokens(gen.prompt_tokens, gen.completion_tokens)
        trace.end_span(
            "generate",
            output={"answer": gen.answer, "ttft_ms": gen.ttft_ms, "total_ms": gen.total_ms},
        )
        trace.generation(
            name="chat_completion",
            model=gen.model,
            input_data={"question": question, "doc_ids": doc_ids},
            output=gen.answer,
            usage={
                "input": gen.prompt_tokens,
                "output": gen.completion_tokens,
                "total": gen.prompt_tokens + gen.completion_tokens,
            },
            metadata={"prompt_version": prompt_version},
        )

        # --- store caches ---
        cached = CachedAnswer(
            answer=gen.answer,
            doc_ids=doc_ids,
            chunk_ids=chunk_ids,
            model=model,
            prompt_version=prompt_version,
        )
        if cache_enabled:
            exact_key = self.exact.set(question, model, prompt_version, cached)
            self.semantic.store(
                entry_id=exact_key.replace("exact:", "sem:"),
                query_embedding=query_embedding,
                model=model,
                prompt_version=prompt_version,
                value=cached,
            )

        timings.e2e_ms = (time.perf_counter() - e2e_start) * 1000
        return AskResult(
            answer=gen.answer,
            cache="MISS",
            doc_ids=doc_ids,
            chunk_ids=chunk_ids,
            timings=timings,
            prompt_tokens=gen.prompt_tokens,
            completion_tokens=gen.completion_tokens,
            model=model,
            prompt_version=prompt_version,
            request_id=trace.request_id,
            semantic_similarity=semantic_sim,
            cache_enabled=cache_enabled,
            chunks=chunks,
        )
