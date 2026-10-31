from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import get_settings
from app.observability.metrics import set_eval_score
from app.observability.tracing import get_langfuse
from app.rag.pipeline import RagPipeline
from evals.judges import judge_answer, keyword_overlap


@dataclass
class RowResult:
    id: str
    question: str
    hit_at_k: int
    mrr: float
    keyword_overlap: float
    faithfulness: float | None
    relevance: float | None
    cache: str
    e2e_ms: float
    retrieved_doc_ids: list[str]
    answer: str


def load_golden(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def hit_at_k(expected: list[str], retrieved: list[str]) -> int:
    return int(any(doc in retrieved for doc in expected))


def reciprocal_rank(expected: list[str], retrieved: list[str]) -> float:
    for i, doc in enumerate(retrieved, start=1):
        if doc in expected:
            return 1.0 / i
    return 0.0


def run(
    dataset_path: Path,
    use_cache: bool,
    judge: bool,
    limit: int | None,
    output_path: Path,
) -> dict:
    settings = get_settings()
    pipeline = RagPipeline(settings)
    rows = load_golden(dataset_path)
    if limit:
        rows = rows[:limit]

    results: list[RowResult] = []
    for row in rows:
        start = time.perf_counter()
        ask = pipeline.ask(row["question"], use_cache=use_cache)
        # Prefer unique doc order from retrieval; fall back to cached ids
        retrieved_docs = ask.doc_ids
        expected = row["expected_doc_ids"]
        context = "\n\n".join(c.text for c in ask.chunks) if ask.chunks else "(cached; no chunk text)"
        faith = rel = None
        if judge and ask.cache == "MISS":
            scores = judge_answer(row["question"], context, ask.answer)
            faith = scores.faithfulness
            rel = scores.relevance
        elif judge and ask.cache != "MISS":
            # Still judge answer vs reference-less context note
            scores = judge_answer(row["question"], context, ask.answer)
            faith = scores.faithfulness
            rel = scores.relevance

        result = RowResult(
            id=row["id"],
            question=row["question"],
            hit_at_k=hit_at_k(expected, retrieved_docs) if ask.cache == "MISS" else hit_at_k(expected, retrieved_docs),
            mrr=reciprocal_rank(expected, retrieved_docs),
            keyword_overlap=keyword_overlap(row["reference_answer"], ask.answer),
            faithfulness=faith,
            relevance=rel,
            cache=ask.cache,
            e2e_ms=ask.timings.e2e_ms or (time.perf_counter() - start) * 1000,
            retrieved_doc_ids=retrieved_docs,
            answer=ask.answer,
        )
        results.append(result)
        print(
            f"{result.id} cache={result.cache} hit@k={result.hit_at_k} "
            f"mrr={result.mrr:.2f} overlap={result.keyword_overlap:.2f} "
            f"faith={result.faithfulness} rel={result.relevance} e2e_ms={result.e2e_ms:.0f}"
        )

    hit_rate = statistics.mean(r.hit_at_k for r in results) if results else 0.0
    mrr = statistics.mean(r.mrr for r in results) if results else 0.0
    overlap = statistics.mean(r.keyword_overlap for r in results) if results else 0.0
    faith_vals = [r.faithfulness for r in results if r.faithfulness is not None]
    rel_vals = [r.relevance for r in results if r.relevance is not None]
    summary = {
        "n": len(results),
        "hit_at_k": hit_rate,
        "mrr": mrr,
        "keyword_overlap": overlap,
        "faithfulness_mean": statistics.mean(faith_vals) if faith_vals else None,
        "relevance_mean": statistics.mean(rel_vals) if rel_vals else None,
        "e2e_ms_p50": statistics.median(r.e2e_ms for r in results) if results else None,
        "prompt_version": settings.prompt_version,
        "model": settings.chat_model,
        "use_cache": use_cache,
        "semantic_threshold": settings.semantic_cache_threshold,
    }

    score_map = {
        "hit_at_k": hit_rate,
        "mrr": mrr,
        "keyword_overlap": overlap,
    }
    if summary["faithfulness_mean"] is not None:
        score_map["faithfulness"] = float(summary["faithfulness_mean"])
    if summary["relevance_mean"] is not None:
        score_map["relevance"] = float(summary["relevance_mean"])
    for name, value in score_map.items():
        set_eval_score(name, value)

    # Push gauges to the running API so Grafana can scrape them
    try:
        import httpx

        httpx.post(
            "http://localhost:8000/evals/scores",
            json={"scores": score_map},
            timeout=5.0,
        )
    except Exception as exc:
        print(f"Could not push scores to API /evals/scores: {exc}")

    report = {"summary": summary, "results": [asdict(r) for r in results]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lf = get_langfuse()
    if lf is not None:
        try:
            for r in results:
                trace = lf.trace(
                    name="eval_row",
                    input={"id": r.id, "question": r.question},
                    output={"answer": r.answer},
                    metadata={"dataset": str(dataset_path)},
                )
                if r.faithfulness is not None:
                    trace.score(name="faithfulness", value=r.faithfulness)
                if r.relevance is not None:
                    trace.score(name="relevance", value=r.relevance)
                trace.score(name="hit_at_k", value=float(r.hit_at_k))
                trace.score(name="mrr", value=r.mrr)
            lf.score(
                name="eval_hit_at_k_mean",
                value=hit_rate,
                comment=f"dataset={dataset_path.name} n={len(results)}",
            )
            lf.flush()
        except Exception as exc:
            print(f"Langfuse score push skipped: {exc}")

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG offline evals")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "datasets" / "golden.jsonl",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable cache during eval")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM-as-judge")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval_report.json"),
    )
    args = parser.parse_args()
    run(
        dataset_path=args.dataset,
        use_cache=not args.no_cache,
        judge=not args.no_judge,
        limit=args.limit,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
