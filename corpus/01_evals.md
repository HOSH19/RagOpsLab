# Evals in AI Engineering

Evals measure whether an LLM system does what you intend. Offline evals run on a fixed golden dataset before deploy. Online evals sample production traffic.

## Golden datasets

A golden set pairs inputs with expected outputs or labels. For RAG, each row often includes:
- the user question
- expected source document ids (for retrieval checks)
- a reference answer (for answer quality)

Keep the set small but diverse: factual lookups, multi-hop questions, and out-of-scope queries.

## Retrieval metrics

Hit@k is 1 if any expected document appears in the top-k retrieved chunks, else 0. Mean Reciprocal Rank (MRR) averages 1/rank of the first relevant doc. High Hit@k with low answer quality usually means generation or grounding failed, not retrieval.

## LLM-as-judge

An LLM can score faithfulness (answer supported by context) and relevance (answer addresses the question) on a 1–5 scale. Judges are noisy: use clear rubrics, temperature 0, and spot-check disagreements with humans.

## Regression workflow

Change one variable at a time (prompt, chunk size, model, cache threshold). Re-run the same golden set and compare Hit@k, faithfulness, and latency. Treat score drops as release blockers.
