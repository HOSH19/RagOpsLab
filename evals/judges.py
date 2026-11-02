from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.config import get_settings
from app.llm import get_openai_client

JUDGE_SYSTEM = """You are an evaluation judge. Score the assistant answer.
Return ONLY valid JSON with keys faithfulness and relevance, each an integer 1-5.
faithfulness: is the answer supported by the context? (5=fully grounded, 1=mostly invented)
relevance: does the answer address the question? (5=directly answers, 1=off-topic)
"""


@dataclass
class JudgeScores:
    faithfulness: float
    relevance: float
    raw: str


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def judge_answer(question: str, context: str, answer: str) -> JudgeScores:
    settings = get_settings()
    client = get_openai_client()
    user = (
        f"Question:\n{question}\n\nContext:\n{context}\n\nAnswer:\n{answer}\n\n"
        "Respond with JSON only."
    )
    resp = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content or "{}"
    data = _extract_json(raw)
    return JudgeScores(
        faithfulness=float(data.get("faithfulness", 0)),
        relevance=float(data.get("relevance", 0)),
        raw=raw,
    )


def keyword_overlap(reference: str, answer: str) -> float:
    ref_tokens = {t for t in re.findall(r"[a-z0-9]+", reference.lower()) if len(t) > 2}
    ans_tokens = {t for t in re.findall(r"[a-z0-9]+", answer.lower()) if len(t) > 2}
    if not ref_tokens:
        return 0.0
    return len(ref_tokens & ans_tokens) / len(ref_tokens)
