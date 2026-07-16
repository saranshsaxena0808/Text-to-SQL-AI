import os
import re
from collections.abc import Callable

from app.application.interfaces.runtime import TargetRuntime, TargetRuntimeFactory, TargetSchemaGateway
from app.config.settings import ExecutionSettings
from app.domain.entities.data_source import DataSource
from app.domain.exceptions import DataSourceNotFoundError, DatabaseConnectionError
from app.domain.ports.unit_of_work import UnitOfWork
from app.infrastructure.execution import SqlAlchemyReadOnlyExecutor
from app.infrastructure.guardrails import (
    LoggingGuardrailAuditSink, PostgresQueryPlanEstimator, SqlGlotPostgresParser,
)
from app.application.services.guardrail_service import GuardrailEngine
from app.domain.entities.guardrails import GuardrailPolicy
from app.infrastructure.schema import SqlAlchemySchemaExtractor
from app.infrastructure.target_database.engine_registry import TargetEngineRegistry


_ENV_REFERENCE = re.compile(r"^env://([A-Z][A-Z0-9_]{1,127})$")


class EnvironmentSecretResolver:
    def resolve(self, reference: str) -> str:
        match = _ENV_REFERENCE.fullmatch(reference)
        if not match:
            raise DatabaseConnectionError("Only env:// secret references are configured")
        value = os.environ.get(match.group(1))
        if not value:
            raise DatabaseConnectionError("Referenced database secret is unavailable")
        return value


class ProductionTargetRuntimeFactory(TargetRuntimeFactory):
    def __init__(self, uow_factory: Callable[[], UnitOfWork], registry: TargetEngineRegistry,
                 secrets: EnvironmentSecretResolver, policy: GuardrailPolicy,
                 execution_settings: ExecutionSettings) -> None:
        self._uow_factory, self._registry, self._secrets = uow_factory, registry, secrets
        self._policy, self._execution_settings = policy, execution_settings

    def create(self, data_source_id, tenant_id) -> TargetRuntime:
        with self._uow_factory() as uow:
            source = uow.data_sources.get(data_source_id, tenant_id)
        if source is None:
            raise DataSourceNotFoundError("Data source was not found")
        url = self._secrets.resolve(source.secret_ref)
        engine = self._registry.get_or_create(f"{tenant_id}:{data_source_id}", url)
        plans = PostgresQueryPlanEstimator(engine)
        return TargetRuntime(
            guardrails=GuardrailEngine(SqlGlotPostgresParser(), self._policy,
                                       LoggingGuardrailAuditSink(), plans),
            executor=SqlAlchemyReadOnlyExecutor(engine, self._execution_settings, plans),
        )


class ProductionTargetSchemaGateway(TargetSchemaGateway):
    def __init__(self, registry: TargetEngineRegistry, secrets: EnvironmentSecretResolver,
                 extractor: SqlAlchemySchemaExtractor) -> None:
        self._registry, self._secrets, self._extractor = registry, secrets, extractor

    def extract(self, data_source: DataSource):
        engine = self._registry.get_or_create(str(data_source.id),
                                              self._secrets.resolve(data_source.secret_ref))
        return self._extractor.extract(engine, data_source.id)
