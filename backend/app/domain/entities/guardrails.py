from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ColumnReference(BaseModel):
    model_config = ConfigDict(frozen=True)
    table: str | None = None
    name: str


class SqlAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)
    statement_count: int
    statement_type: str
    tables: tuple[str, ...] = ()
    table_aliases: dict[str, str] = Field(default_factory=dict)
    columns: tuple[ColumnReference, ...] = ()
    functions: tuple[str, ...] = ()
    has_nested_query: bool = False
    has_locking_clause: bool = False
    has_select_into: bool = False
    join_count: int = 0
    aggregate_functions: tuple[str, ...] = ()
    has_group_by: bool = False
    predicate_columns: tuple[str, ...] = ()
    limit: int | None = None


class QueryPlanEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_cost: float = Field(ge=0)
    estimated_rows: int = Field(ge=0)
    plan: dict[str, Any] = Field(default_factory=dict)


class GuardrailViolation(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GuardrailDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    allowed: bool
    original_sql: str
    executable_sql: str | None = None
    injected_limit: bool = False
    plan: QueryPlanEstimate | None = None
    violations: tuple[GuardrailViolation, ...] = ()


class GuardrailPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str = Field(min_length=1, max_length=64)
    default_limit: int = Field(default=500, ge=1, le=10000)
    max_sql_length: int = Field(default=100000, ge=1, le=1000000)
    reject_nested_queries: bool = True
    explain_enabled: bool = True
    max_plan_cost: float = Field(default=100000.0, gt=0)
    max_estimated_rows: int = Field(default=1000000, ge=1)
    blocked_functions: tuple[str, ...] = (
        "pg_sleep", "dblink", "dblink_exec", "lo_import", "lo_export",
        "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
        "set_config", "setval", "nextval", "pg_advisory_lock", "pg_advisory_xact_lock",
    )
