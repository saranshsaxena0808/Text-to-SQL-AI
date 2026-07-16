from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.entities.data_source import DataSource, DataSourceStatus
from app.domain.entities.schema import SchemaSnapshot
from app.domain.entities.query import Feedback, QueryRun, QueryStatus
from app.domain.exceptions import RepositoryError
from app.domain.ports.repositories import (
    DataSourceRepository, FeedbackRepository, QueryRunRepository, SchemaSnapshotRepository,
)
from app.infrastructure.persistence.sqlalchemy.models import (
    DataSourceModel, FeedbackModel, QueryRunModel, SchemaSnapshotModel,
)


def _source_entity(model: DataSourceModel) -> DataSource:
    return DataSource(
        id=model.id, tenant_id=model.tenant_id, name=model.name, secret_ref=model.secret_ref,
        status=DataSourceStatus(model.status), options=model.options,
        created_at=model.created_at, updated_at=model.updated_at,
    )


class SqlAlchemyDataSourceRepository(DataSourceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, data_source: DataSource) -> None:
        self._session.add(DataSourceModel(**data_source.model_dump(mode="python")))

    def get(self, data_source_id: UUID, tenant_id: UUID) -> DataSource | None:
        statement = select(DataSourceModel).where(
            DataSourceModel.id == data_source_id, DataSourceModel.tenant_id == tenant_id
        )
        model = self._session.scalar(statement)
        return _source_entity(model) if model else None

    def list_for_tenant(self, tenant_id: UUID) -> list[DataSource]:
        statement: Select[tuple[DataSourceModel]] = select(DataSourceModel).where(
            DataSourceModel.tenant_id == tenant_id
        )
        return [_source_entity(item) for item in self._session.scalars(statement)]


class SqlAlchemySchemaSnapshotRepository(SchemaSnapshotRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, snapshot: SchemaSnapshot, tenant_id: UUID) -> None:
        self._session.add(SchemaSnapshotModel(
            tenant_id=tenant_id, data_source_id=snapshot.data_source_id,
            checksum=snapshot.checksum, dialect=snapshot.dialect,
            captured_at=snapshot.captured_at,
            structured_schema=snapshot.model_dump(mode="json"),
        ))

    def latest(self, data_source_id: UUID, tenant_id: UUID) -> SchemaSnapshot | None:
        statement = (
            select(SchemaSnapshotModel)
            .where(SchemaSnapshotModel.data_source_id == data_source_id,
                   SchemaSnapshotModel.tenant_id == tenant_id)
            .order_by(desc(SchemaSnapshotModel.captured_at)).limit(1)
        )
        try:
            model = self._session.scalar(statement)
            return SchemaSnapshot.model_validate(model.structured_schema) if model else None
        except SQLAlchemyError as exc:
            raise RepositoryError("Unable to load schema snapshot") from exc


def _query_entity(model: QueryRunModel) -> QueryRun:
    return QueryRun(id=model.id, tenant_id=model.tenant_id, user_id=model.user_id,
                    data_source_id=model.data_source_id, question=model.question,
                    generated_sql_redacted=model.generated_sql_redacted,
                    status=QueryStatus(model.status), model=model.model,
                    prompt_version=model.prompt_version, confidence=model.confidence,
                    evaluation=model.evaluation, timings=model.timings,
                    warnings=tuple(model.warnings), created_at=model.created_at)


class SqlAlchemyQueryRunRepository(QueryRunRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, query_run: QueryRun) -> None:
        payload = query_run.model_dump(mode="python")
        payload["status"] = query_run.status.value
        payload["warnings"] = list(query_run.warnings)
        self._session.add(QueryRunModel(**payload))

    def get(self, query_run_id: UUID, tenant_id: UUID) -> QueryRun | None:
        model = self._session.scalar(select(QueryRunModel).where(
            QueryRunModel.id == query_run_id, QueryRunModel.tenant_id == tenant_id))
        return _query_entity(model) if model else None

    def list_for_tenant(self, tenant_id: UUID, limit: int, offset: int = 0) -> list[QueryRun]:
        statement = (select(QueryRunModel).where(QueryRunModel.tenant_id == tenant_id)
                     .order_by(desc(QueryRunModel.created_at)).offset(offset).limit(limit))
        return [_query_entity(model) for model in self._session.scalars(statement)]


class SqlAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, feedback: Feedback) -> None:
        self._session.add(FeedbackModel(**feedback.model_dump(mode="python")))
