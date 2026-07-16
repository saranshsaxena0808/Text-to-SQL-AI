from collections.abc import Sequence
from threading import RLock
from typing import Any

from app.domain.exceptions import RetrievalError
from app.domain.ports.retrieval import EmbeddingProvider


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Lazy Sentence Transformers adapter; model loading occurs on first use."""

    def __init__(self, model_name: str, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        self._model_name = model_name
        self._dimension = dimension
        self._model: Any | None = None
        self._lock = RLock()

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        if vectors.shape[1] != self._dimension:
            raise RetrievalError(
                f"Configured dimension {self._dimension} does not match model dimension {vectors.shape[1]}"
            )
        return vectors.astype("float32").tolist()

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise RetrievalError("sentence-transformers dependency is not installed") from exc
                self._model = SentenceTransformer(self._model_name)
            return self._model
