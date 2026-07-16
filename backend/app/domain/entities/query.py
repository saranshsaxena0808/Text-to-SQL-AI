from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class QueryStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CLARIFICATION_REQUIRED = "clarification_required"
    FAILED = "failed"


class QueryRun(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    data_source_id: UUID
    question: str
    generated_sql_redacted: str | None = None
    status: QueryStatus
    model: str | None = None
    prompt_version: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evaluation: dict[str, object] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    created_at: datetime


class Feedback(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    query_run_id: UUID
    user_id: UUID
    rating: int = Field(ge=1, le=5)
    correction_sql: str | None = Field(default=None, max_length=100000)
    comment: str | None = Field(default=None, max_length=4000)
    created_at: datetime
