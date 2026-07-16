from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from app.application.interfaces.runtime import TargetSchemaGateway
from app.domain.entities.data_source import DataSource
from app.domain.entities.query import Feedback, QueryRun
from app.domain.exceptions import DataSourceNotFoundError
from app.domain.ports.unit_of_work import UnitOfWork


class DataSourceService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, tenant_id: UUID, name: str, secret_ref: str,
               options: dict[str, object] | None = None) -> DataSource:
        now = datetime.now(timezone.utc)
        source = DataSource(tenant_id=tenant_id, name=name, secret_ref=secret_ref,
                            options=options or {}, created_at=now, updated_at=now)
        with self._uow_factory() as uow:
            uow.data_sources.add(source)
            uow.commit()
        return source

    def list(self, tenant_id: UUID) -> list[DataSource]:
        with self._uow_factory() as uow:
            return uow.data_sources.list_for_tenant(tenant_id)


class SchemaApplicationService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], gateway: TargetSchemaGateway) -> None:
        self._uow_factory, self._gateway = uow_factory, gateway

    def get(self, tenant_id: UUID, data_source_id: UUID):
        with self._uow_factory() as uow:
            snapshot = uow.schema_snapshots.latest(data_source_id, tenant_id)
        if snapshot is None:
            raise DataSourceNotFoundError("Schema snapshot was not found")
        return snapshot

    def refresh(self, tenant_id: UUID, data_source_id: UUID):
        with self._uow_factory() as uow:
            source = uow.data_sources.get(data_source_id, tenant_id)
        if source is None:
            raise DataSourceNotFoundError("Data source was not found")
        snapshot = self._gateway.extract(source)
        with self._uow_factory() as uow:
            uow.schema_snapshots.add(snapshot, tenant_id)
            uow.commit()
        return snapshot


class HistoryService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def get(self, tenant_id: UUID, query_run_id: UUID) -> QueryRun | None:
        with self._uow_factory() as uow:
            return uow.query_runs.get(query_run_id, tenant_id)

    def list(self, tenant_id: UUID, limit: int, offset: int) -> list[QueryRun]:
        with self._uow_factory() as uow:
            return uow.query_runs.list_for_tenant(tenant_id, limit, offset)


class FeedbackService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def create(self, tenant_id: UUID, user_id: UUID, query_run_id: UUID, rating: int,
               correction_sql: str | None, comment: str | None) -> Feedback:
        with self._uow_factory() as uow:
            if uow.query_runs.get(query_run_id, tenant_id) is None:
                raise DataSourceNotFoundError("Query run was not found")
            item = Feedback(tenant_id=tenant_id, user_id=user_id, query_run_id=query_run_id,
                            rating=rating, correction_sql=correction_sql, comment=comment,
                            created_at=datetime.now(timezone.utc))
            uow.feedback.add(item)
            uow.commit()
        return item
