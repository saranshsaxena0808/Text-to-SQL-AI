from abc import ABC, abstractmethod
from types import TracebackType

from app.domain.ports.repositories import (
    DataSourceRepository, FeedbackRepository, QueryRunRepository, SchemaSnapshotRepository,
)


class UnitOfWork(ABC):
    data_sources: DataSourceRepository
    schema_snapshots: SchemaSnapshotRepository
    query_runs: QueryRunRepository
    feedback: FeedbackRepository

    @abstractmethod
    def __enter__(self) -> "UnitOfWork": ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
