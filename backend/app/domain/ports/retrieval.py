from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorIndex(ABC):
    @abstractmethod
    def rebuild(self, keys: Sequence[str], vectors: Sequence[Sequence[float]], version: str) -> None: ...

    @abstractmethod
    def search(self, vector: Sequence[float], limit: int) -> list[tuple[str, float]]: ...

    @property
    @abstractmethod
    def version(self) -> str | None: ...
