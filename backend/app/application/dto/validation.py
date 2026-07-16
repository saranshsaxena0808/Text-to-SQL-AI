from dataclasses import dataclass

from app.application.dto.execution import SqlExecutionResult
from app.domain.entities.guardrails import SqlAnalysis
from app.domain.entities.schema import SchemaSnapshot


@dataclass(frozen=True, slots=True)
class HallucinationContext:
    question: str
    sql: str
    explanation: str
    analysis: SqlAnalysis
    schema: SchemaSnapshot
    execution: SqlExecutionResult | None
    execution_succeeded: bool
    candidate_sql: tuple[str, ...] = ()
