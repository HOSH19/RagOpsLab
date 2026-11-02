from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    client = get_openai_client()
    response = client.embeddings.create(model=settings.embedding_model, input=texts)
    # API returns in input order
    by_index = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in by_index]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
