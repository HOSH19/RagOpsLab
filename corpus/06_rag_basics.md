# RAG Basics

Retrieval-Augmented Generation (RAG) grounds an LLM on documents you control. The model answers using retrieved context instead of relying only on parametric memory.

## Pipeline

1. Ingest: split documents into chunks, embed each chunk, store vectors.
2. Retrieve: embed the user query, find top-k similar chunks.
3. Generate: prompt the LLM with the question plus retrieved context; ask it to cite or stay faithful to sources.

## Chunking

Chunk size trades recall against precision. Very small chunks improve matching specific facts but lose surrounding context. Very large chunks dilute similarity and burn tokens. Overlap between chunks reduces boundary misses.

## Failure modes

- Retrieval miss: right answer exists but was not retrieved → fix chunking, embeddings, or k.
- Hallucination: chunks retrieved but answer invents unsupported claims → fix prompt, add citations, or use a stronger model.
- Out of scope: no relevant docs → the system should refuse rather than guess.
