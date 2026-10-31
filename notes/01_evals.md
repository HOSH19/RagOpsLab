# Evals

Evals answer: **does this LLM system do what we intend?** They turn “feels okay in chat” into measurable quality you can compare across prompts, models, chunk sizes, and cache settings.

## Offline vs online

| Kind | When | What |
|------|------|------|
| **Offline** | Before ship / on every change | Fixed golden dataset; repeatable scores |
| **Online** | In production | Sample live traffic; user feedback, judges, heuristics |

This lab focuses on **offline** evals (`python -m evals.run_evals`). Same idea as unit tests: freeze inputs, measure outputs, fail on regressions.

## Golden datasets

A golden row usually has:

- **question** — realistic user input
- **expected_doc_ids** — which corpus docs should be retrieved (RAG-specific)
- **reference_answer** — a short “good enough” answer for overlap / human checks

See [`evals/datasets/golden.jsonl`](../evals/datasets/golden.jsonl). Keep the set small but diverse: facts, paraphrases, multi-hop, and out-of-scope.

## Retrieval metrics

Before judging the prose, check whether the right context arrived.

- **Hit@k** — 1 if any expected `doc_id` appears in the top-k retrieved docs, else 0. Report the mean over the dataset.
- **MRR (Mean Reciprocal Rank)** — average of `1/rank` of the first relevant doc. Rewards putting the right doc higher.

High Hit@k + bad answers ⇒ generation/prompt problem.  
Low Hit@k ⇒ chunking, embeddings, `TOP_K`, or corpus gaps.

## Answer metrics

- **Keyword / token overlap** — cheap proxy vs the reference answer (noisy; good as a smoke check).
- **LLM-as-judge** — another model scores **faithfulness** (supported by context?) and **relevance** (answers the question?) on a 1–5 rubric (`evals/judges.py`).

Judges are imperfect: use temperature 0, a clear rubric, and spot-check disagreements.

## Regression workflow

1. Run evals on the current prompt/model → save `data/eval_report.json`.
2. Change **one** knob (`PROMPT_VERSION`, chunk size, cache threshold, model).
3. Re-run the **same** golden set.
4. Compare Hit@k, faithfulness, relevance, and e2e latency.

In this lab, try `PROMPT_VERSION=rag-answer-v0-broken` vs `rag-answer-v1`: latency stays similar; faithfulness should collapse.

## How it shows up in RagOpsLab

- Runner: `evals/run_evals.py`
- Scores → JSON report, optional Langfuse scores, and `POST /evals/scores` for Grafana gauges (`rag_eval_score`)
