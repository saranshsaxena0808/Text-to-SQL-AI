from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.data_source import DataSourceStatus
from app.domain.entities.query import QueryStatus


class QueryRequest(BaseModel):
    data_source_id: UUID
    question: str = Field(min_length=1, max_length=5000)
    model: str = Field(min_length=1, max_length=200)


class EditedSqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=100000)


class ConfidenceResponse(BaseModel):
    score: float
    breakdown: list[dict[str, Any]]
    warnings: list[str]
    policy_version: str


class HallucinationResponse(BaseModel):
    probability: float
    explanation: str
    evidence: list[dict[str, Any]]
    policy_version: str


class QueryResponse(BaseModel):
    query_run_id: UUID
    status: QueryStatus
    generated_sql: str | None
    explanation: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    execution_time_ms: float | None = None
    confidence: ConfidenceResponse | None = None
    hallucination: HallucinationResponse | None = None
    warnings: list[str] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    clarification_question: str | None = None


class DataSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    secret_ref: str = Field(min_length=1, max_length=1024)
    options: dict[str, Any] = Field(default_factory=dict)


class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    status: DataSourceStatus
    created_at: datetime


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    correction_sql: str | None = Field(default=None, max_length=100000)
    comment: str | None = Field(default=None, max_length=4000)


class FeedbackResponse(BaseModel):
    id: UUID
    query_run_id: UUID
    rating: int
    created_at: datetime


class QueryHistoryResponse(BaseModel):
    id: UUID
    data_source_id: UUID
    question: str
    generated_sql: str | None
    status: QueryStatus
    model: str | None
    confidence: float | None
    warnings: list[str]
    timings: dict[str, float]
    created_at: datetime


class HistoryPageResponse(BaseModel):
    items: list[QueryHistoryResponse]
    limit: int
    offset: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool] = Field(default_factory=dict)
