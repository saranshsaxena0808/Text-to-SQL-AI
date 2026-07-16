from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.guardrails import GuardrailDecision, QueryPlanEstimate, SqlAnalysis


class SqlParser(ABC):
    @abstractmethod
    def analyze(self, sql: str) -> SqlAnalysis: ...

    @abstractmethod
    def enforce_limit(self, sql: str, maximum: int) -> tuple[str, bool]: ...

    @abstractmethod
    def sanitize(self, sql: str) -> str: ...


class QueryPlanEstimator(ABC):
    @abstractmethod
    def estimate(self, sql: str) -> QueryPlanEstimate: ...


class GuardrailAuditSink(ABC):
    @abstractmethod
    def record_blocked(self, decision: GuardrailDecision, sanitized_sql: str,
                       query_run_id: UUID | None = None) -> None: ...
