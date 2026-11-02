from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass

import redis

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class CachedAnswer:
    answer: str
    doc_ids: list[str]
    chunk_ids: list[str]
    model: str
    prompt_version: str


class ExactCache:
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
                logger.warning("Redis unavailable for exact cache: %s", exc)
                self._unavailable = True
                self._client = None
        return self._client

    @staticmethod
    def normalize_query(query: str) -> str:
        return " ".join(query.lower().strip().split())

    def make_key(self, query: str, model: str, prompt_version: str) -> str:
        payload = f"{self.normalize_query(query)}|{model}|{prompt_version}"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"exact:{digest}"

    def get(self, query: str, model: str, prompt_version: str) -> CachedAnswer | None:
        client = self.client
        if client is None:
            return None
        try:
            key = self.make_key(query, model, prompt_version)
            raw = client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return CachedAnswer(**data)
        except Exception as exc:
            logger.warning("Exact cache get failed: %s", exc)
            self._unavailable = True
            return None

    def set(self, query: str, model: str, prompt_version: str, value: CachedAnswer) -> str:
        key = self.make_key(query, model, prompt_version)
        client = self.client
        if client is None:
            return key
        try:
            client.setex(key, self.settings.cache_ttl_seconds, json.dumps(asdict(value)))
        except Exception as exc:
            logger.warning("Exact cache set failed: %s", exc)
            self._unavailable = True
        return key
