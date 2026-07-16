from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.entities.guardrails import GuardrailViolation
from app.domain.entities.hallucination import ConfidenceAssessment, HallucinationAssessment
from app.domain.entities.query import QueryStatus


@dataclass(frozen=True, slots=True)
class QueryCommand:
    tenant_id: UUID
    user_id: UUID
    data_source_id: UUID
    question: str
    model: str


@dataclass(frozen=True, slots=True)
class EditedSqlCommand:
    tenant_id: UUID
    user_id: UUID
    data_source_id: UUID
    query_run_id: UUID
    question: str
    sql: str


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    query_run_id: UUID
    status: QueryStatus
    generated_sql: str | None
    explanation: str
    rows: tuple[dict[str, Any], ...] = ()
    columns: tuple[str, ...] = ()
    execution_time_ms: float | None = None
    confidence: ConfidenceAssessment | None = None
    hallucination: HallucinationAssessment | None = None
    warnings: tuple[str, ...] = ()
    violations: tuple[GuardrailViolation, ...] = ()
    clarification_question: str | None = None
