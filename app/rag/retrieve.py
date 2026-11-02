from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.llm import embed_query
from app.rag.ingest import get_collection


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    source: str
    text: str
    distance: float


def retrieve(query: str, query_embedding: list[float] | None = None, settings: Settings | None = None) -> list[RetrievedChunk]:
    settings = settings or get_settings()
    collection = get_collection(settings)
    embedding = query_embedding if query_embedding is not None else embed_query(query)
    result = collection.query(
        query_embeddings=[embedding],
        n_results=settings.top_k,
        include=["documents", "metadatas", "distances"],
    )
    chunks: list[RetrievedChunk] = []
    ids = result["ids"][0] if result["ids"] else []
    docs = result["documents"][0] if result["documents"] else []
    metas = result["metadatas"][0] if result["metadatas"] else []
    dists = result["distances"][0] if result["distances"] else []
    for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=str(meta.get("doc_id", "")),
                source=str(meta.get("source", "")),
                text=text,
                distance=float(dist),
            )
        )
    return chunks
