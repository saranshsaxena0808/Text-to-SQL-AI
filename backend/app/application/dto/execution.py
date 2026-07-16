from dataclasses import dataclass

import pandas as pd

from app.domain.entities.guardrails import QueryPlanEstimate


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    name: str
    data_type: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    columns: tuple[ColumnMetadata, ...]
    statement_timeout_ms: int
    lock_timeout_ms: int
    truncated: bool
    dialect: str = "postgresql"


@dataclass(frozen=True, slots=True)
class SqlExecutionResult:
    dataframe: pd.DataFrame
    execution_time_ms: float
    rows_returned: int
    explain_plan: QueryPlanEstimate
    metadata: ExecutionMetadata
