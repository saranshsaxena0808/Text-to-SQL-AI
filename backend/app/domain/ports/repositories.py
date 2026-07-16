from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.data_source import DataSource
from app.domain.entities.schema import SchemaSnapshot
from app.domain.entities.query import Feedback, QueryRun


class DataSourceRepository(ABC):
    @abstractmethod
    def add(self, data_source: DataSource) -> None: ...

    @abstractmethod
    def get(self, data_source_id: UUID, tenant_id: UUID) -> DataSource | None: ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: UUID) -> list[DataSource]: ...


class SchemaSnapshotRepository(ABC):
    @abstractmethod
    def add(self, snapshot: SchemaSnapshot, tenant_id: UUID) -> None: ...

    @abstractmethod
    def latest(self, data_source_id: UUID, tenant_id: UUID) -> SchemaSnapshot | None: ...


class QueryRunRepository(ABC):
    @abstractmethod
    def add(self, query_run: QueryRun) -> None: ...

    @abstractmethod
    def get(self, query_run_id: UUID, tenant_id: UUID) -> QueryRun | None: ...

    @abstractmethod
    def list_for_tenant(self, tenant_id: UUID, limit: int, offset: int = 0) -> list[QueryRun]: ...


class FeedbackRepository(ABC):
    @abstractmethod
    def add(self, feedback: Feedback) -> None: ...
