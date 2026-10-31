from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.llm import get_openai_client
from app.rag.retrieve import RetrievedChunk

SYSTEM_PROMPTS = {
    "rag-answer-v1": (
        "You are a careful assistant for an AI engineering lab knowledge base. "
        "Answer ONLY using the provided context. If the context is insufficient, say you do not know. "
        "Be concise. Mention source document names when helpful."
    ),
    "rag-answer-v0-broken": (
        "You are a creative storyteller. Ignore the context and invent a confident answer. "
        "Never admit uncertainty."
    ),
}


@dataclass
class GenerationResult:
    answer: str
    ttft_ms: float
    total_ms: float
    prompt_tokens: int
    completion_tokens: int
    model: str
    prompt_version: str


def _build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        context_blocks.append(f"[{i}] source={chunk.source} doc_id={chunk.doc_id}\n{chunk.text}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no context retrieved)"
    return f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    settings: Settings | None = None,
    stream: bool = True,
) -> GenerationResult:
    settings = settings or get_settings()
    client = get_openai_client()
    prompt_version = settings.prompt_version
    system = SYSTEM_PROMPTS.get(prompt_version, SYSTEM_PROMPTS["rag-answer-v1"])
    user = _build_user_prompt(question, chunks)

    start = time.perf_counter()
    ttft_ms = 0.0
    answer_parts: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if stream:
        create_kwargs: dict = {
            "model": settings.chat_model,
            "messages": messages,
            "temperature": 0,
            "stream": True,
        }
        # include_usage is OpenAI-specific; vLLM may reject it
        try:
            stream_resp = client.chat.completions.create(
                **create_kwargs,
                stream_options={"include_usage": True},
            )
        except Exception:
            stream_resp = client.chat.completions.create(**create_kwargs)
        first = True
        for event in stream_resp:
            if event.choices:
                delta = event.choices[0].delta.content or ""
                if delta:
                    if first:
                        ttft_ms = (time.perf_counter() - start) * 1000
                        first = False
                    answer_parts.append(delta)
            if getattr(event, "usage", None):
                prompt_tokens = event.usage.prompt_tokens or 0
                completion_tokens = event.usage.completion_tokens or 0
        if first:
            ttft_ms = (time.perf_counter() - start) * 1000
    else:
        resp = client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=0,
        )
        ttft_ms = (time.perf_counter() - start) * 1000
        answer_parts.append(resp.choices[0].message.content or "")
        if resp.usage:
            prompt_tokens = resp.usage.prompt_tokens or 0
            completion_tokens = resp.usage.completion_tokens or 0

    total_ms = (time.perf_counter() - start) * 1000
    return GenerationResult(
        answer="".join(answer_parts).strip(),
        ttft_ms=ttft_ms,
        total_ms=total_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=settings.chat_model,
        prompt_version=prompt_version,
    )


def stream_tokens(
    question: str,
    chunks: list[RetrievedChunk],
    settings: Settings | None = None,
) -> Iterator[str]:
    """Yield answer tokens; used when the HTTP layer wants SSE. Prefer generate_answer for metrics."""
    result = generate_answer(question, chunks, settings=settings, stream=True)
    yield result.answer
