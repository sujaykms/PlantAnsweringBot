"""Local models: bge-small embedder + MiniLM cross-encoder reranker."""

from functools import lru_cache

from sentence_transformers import CrossEncoder, SentenceTransformer

from app.config import get_settings

# bge-small expects this prefix on queries (not on passages).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embed_model, device="cpu")


@lru_cache
def get_reranker() -> CrossEncoder:
    return CrossEncoder(get_settings().rerank_model, device="cpu")


def embed_passages(texts: list[str]) -> list[list[float]]:
    return get_embedder().encode(texts, normalize_embeddings=True, batch_size=32).tolist()


def embed_query(text: str) -> list[float]:
    return get_embedder().encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def rerank(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return get_reranker().predict([(query, p) for p in passages]).tolist()


def warm_up() -> None:
    embed_query("warm up")
    rerank("warm up", ["warm up"])
