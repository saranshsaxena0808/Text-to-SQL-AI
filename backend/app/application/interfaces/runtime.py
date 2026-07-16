from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.application.interfaces.execution import QueryExecutor
from app.domain.entities.data_source import DataSource
from app.domain.entities.guardrails import GuardrailDecision
from app.domain.entities.schema import SchemaSnapshot


class GuardrailEvaluator(ABC):
    @abstractmethod
    def evaluate(self, sql: str, schema: SchemaSnapshot | None = None,
                 query_run_id: UUID | None = None) -> GuardrailDecision: ...


@dataclass(frozen=True, slots=True)
class TargetRuntime:
    guardrails: GuardrailEvaluator
    executor: QueryExecutor


class TargetRuntimeFactory(ABC):
    @abstractmethod
    def create(self, data_source_id: UUID, tenant_id: UUID) -> TargetRuntime: ...


class TargetSchemaGateway(ABC):
    @abstractmethod
    def extract(self, data_source: DataSource) -> SchemaSnapshot: ...


class ReadinessProbe(ABC):
    @abstractmethod
    def check(self) -> dict[str, bool]: ...
