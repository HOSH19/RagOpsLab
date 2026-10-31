# Prompt Versioning

Treat prompts like code. Give each prompt a version string (for example `rag-answer-v1`) and include that version in cache keys, traces, and eval reports.

## Why version

Changing a system prompt can alter answers for identical user questions. Without versions, exact caches serve outdated instructions and evals cannot attribute score changes.

## Practice

- Store prompts in files or a registry, not only in chat history
- Bump the version on any wording change that could affect behavior
- Record prompt version on every Langfuse trace and every cached entry
- When comparing evals, always note which prompt version produced the scores
