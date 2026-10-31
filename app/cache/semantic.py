from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict

import numpy as np
import redis

from app.cache.exact import CachedAnswer
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class SemanticCache:
    INDEX_KEY = "semantic:index"

    def __init__(self, client: redis.Redis | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self._unavailable = False

    @property
    def client(self) -> redis.Redis | None:
        if self._unavailable:
            return None
        if self._client is None:
            try:
                self._client = redis.from_url(self.settings.redis_url, decode_responses=True)
                self._client.ping()
            except Exception as exc:
                logger.warning("Redis unavailable for semantic cache: %s", exc)
                self._unavailable = True
                self._client = None
        return self._client

    def _entry_key(self, entry_id: str) -> str:
        return f"semantic:entry:{entry_id}"

    def lookup(
        self,
        query_embedding: list[float],
        model: str,
        prompt_version: str,
    ) -> tuple[CachedAnswer | None, float]:
        client = self.client
        if client is None:
            return None, -1.0
        threshold = self.settings.semantic_cache_threshold
        try:
            entry_ids = client.smembers(self.INDEX_KEY)
        except Exception as exc:
            logger.warning("Semantic cache lookup failed: %s", exc)
            self._unavailable = True
            return None, -1.0

        best_sim = -1.0
        best: CachedAnswer | None = None
        now = time.time()
        for entry_id in entry_ids:
            try:
                raw = client.get(self._entry_key(entry_id))
            except Exception:
                continue
            if not raw:
                client.srem(self.INDEX_KEY, entry_id)
                continue
            data = json.loads(raw)
            if data.get("model") != model or data.get("prompt_version") != prompt_version:
                continue
            if data.get("expires_at", 0) < now:
                client.delete(self._entry_key(entry_id))
                client.srem(self.INDEX_KEY, entry_id)
                continue
            sim = cosine_similarity(query_embedding, data["embedding"])
            if sim > best_sim:
                best_sim = sim
                best = CachedAnswer(
                    answer=data["answer"],
                    doc_ids=data["doc_ids"],
                    chunk_ids=data["chunk_ids"],
                    model=data["model"],
                    prompt_version=data["prompt_version"],
                )
        if best is not None and best_sim >= threshold:
            return best, best_sim
        return None, best_sim

    def store(
        self,
        entry_id: str,
        query_embedding: list[float],
        model: str,
        prompt_version: str,
        value: CachedAnswer,
    ) -> None:
        client = self.client
        if client is None:
            return
        expires_at = time.time() + self.settings.cache_ttl_seconds
        payload = {
            **asdict(value),
            "embedding": query_embedding,
            "model": model,
            "prompt_version": prompt_version,
            "expires_at": expires_at,
        }
        key = self._entry_key(entry_id)
        try:
            client.setex(key, self.settings.cache_ttl_seconds, json.dumps(payload))
            client.sadd(self.INDEX_KEY, entry_id)
        except Exception as exc:
            logger.warning("Semantic cache store failed: %s", exc)
            self._unavailable = True
