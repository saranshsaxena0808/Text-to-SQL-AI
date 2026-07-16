from collections.abc import Sequence
from threading import RLock
from typing import Any

from app.domain.exceptions import RetrievalError
from app.domain.ports.retrieval import VectorIndex


class FaissVectorIndex(VectorIndex):
    """In-process cosine-similarity index for one schema snapshot."""

    def __init__(self, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._index: Any | None = None
        self._keys: tuple[str, ...] = ()
        self._version: str | None = None
        self._lock = RLock()

    @property
    def version(self) -> str | None:
        return self._version

    def rebuild(self, keys: Sequence[str], vectors: Sequence[Sequence[float]], version: str) -> None:
        if len(keys) != len(vectors):
            raise ValueError("keys and vectors must have the same length")
        if len(set(keys)) != len(keys):
            raise ValueError("keys must be unique")
        np, faiss = self._dependencies()
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != self._dimension:
            raise ValueError(f"vectors must have dimension {self._dimension}")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(self._dimension)
        index.add(matrix)
        with self._lock:
            self._index, self._keys, self._version = index, tuple(keys), version

    def search(self, vector: Sequence[float], limit: int) -> list[tuple[str, float]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        np, faiss = self._dependencies()
        query = np.asarray([vector], dtype="float32")
        if query.shape != (1, self._dimension):
            raise ValueError(f"query vector must have dimension {self._dimension}")
        with self._lock:
            if self._index is None or not self._keys:
                return []
            faiss.normalize_L2(query)
            scores, positions = self._index.search(query, min(limit, len(self._keys)))
            return [(self._keys[position], max(0.0, min(1.0, (float(score) + 1.0) / 2.0)))
                    for score, position in zip(scores[0], positions[0]) if position >= 0]

    @staticmethod
    def _dependencies() -> tuple[Any, Any]:
        try:
            import faiss
            import numpy as np
        except ImportError as exc:
            raise RetrievalError("faiss-cpu and numpy dependencies are required") from exc
        return np, faiss
