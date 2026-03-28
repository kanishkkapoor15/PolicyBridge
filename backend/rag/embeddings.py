"""Embedding utilities using sentence-transformers, compatible with ChromaDB."""

from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL

_model_cache: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer(EMBEDDING_MODEL)
    return _model_cache


class LocalEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB-compatible embedding function using sentence-transformers."""

    def __call__(self, input: Documents) -> Embeddings:
        model = _get_model()
        embeddings = model.encode(input, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()


def get_embedding_function() -> LocalEmbeddingFunction:
    return LocalEmbeddingFunction()
