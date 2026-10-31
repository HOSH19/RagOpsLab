from __future__ import annotations

import hashlib
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings, get_settings
from app.llm import embed_texts


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _doc_id_from_path(path: Path) -> str:
    # e.g. 01_evals.md -> 01_evals
    return path.stem


def get_collection(settings: Settings | None = None):
    settings = settings or get_settings()
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=settings.chroma_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=settings.collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def ingest_corpus(settings: Settings | None = None, reset: bool = True) -> dict:
    settings = settings or get_settings()
    corpus_dir = Path(settings.corpus_path)
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus path not found: {corpus_dir}")

    if reset:
        Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(settings.collection_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        collection = get_collection(settings)

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for path in sorted(corpus_dir.glob("*.md")):
        doc_id = _doc_id_from_path(path)
        text = path.read_text(encoding="utf-8")
        chunks = _chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}::chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "doc_id": doc_id,
                    "source": path.name,
                    "chunk_index": i,
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest()[:16],
                }
            )

    if not documents:
        raise RuntimeError("No markdown documents found to ingest")

    # Batch embeddings to stay within API limits
    batch_size = 64
    embeddings: list[list[float]] = []
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        embeddings.extend(embed_texts(batch))

    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    return {
        "documents": len({m["doc_id"] for m in metadatas}),
        "chunks": len(ids),
        "collection": settings.collection_name,
    }


if __name__ == "__main__":
    result = ingest_corpus()
    print(f"Ingested {result['chunks']} chunks from {result['documents']} docs into {result['collection']}")
