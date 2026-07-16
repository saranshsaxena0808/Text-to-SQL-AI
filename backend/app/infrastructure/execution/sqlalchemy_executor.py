import hashlib
import time
from collections.abc import Callable
from typing import Any

import pandas as pd
from sqlalchemy import Engine, text
from sqlalchemy.exc import (
    DBAPIError, OperationalError, ProgrammingError, SQLAlchemyError,
)

from app.application.dto.execution import ColumnMetadata, ExecutionMetadata, SqlExecutionResult
from app.application.interfaces.execution import QueryExecutor
from app.config.settings import ExecutionSettings
from app.domain.entities.guardrails import GuardrailDecision, QueryPlanEstimate
from app.domain.exceptions import (
    ExecutionConnectionError, ExecutionDatabaseError, ExecutionQueryError,
    ExecutionRejectedError, ExecutionTimeoutError, QueryPlanError,
)
from app.domain.ports.guardrails import QueryPlanEstimator
from app.infrastructure.observability import get_logger


logger = get_logger(__name__)


class SqlAlchemyReadOnlyExecutor(QueryExecutor):
    """Executes only guardrail-approved SQL in a bounded PostgreSQL read-only transaction."""

    def __init__(self, engine: Engine, settings: ExecutionSettings,
                 plan_estimator: QueryPlanEstimator,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("SqlAlchemyReadOnlyExecutor requires a PostgreSQL engine")
        self._engine = engine
        self._settings = settings
        self._plans = plan_estimator
        self._clock = clock

    def execute(self, decision: GuardrailDecision) -> SqlExecutionResult:
        sql = self._approved_sql(decision)
        sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        started = self._clock()
        transaction = None
        try:
            with self._engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    connection.execute(text(
                        f"SET LOCAL statement_timeout = {self._settings.statement_timeout_ms:d}"
                    ))
                    connection.execute(text(
                        f"SET LOCAL lock_timeout = {self._settings.lock_timeout_ms:d}"
                    ))
                    cursor = connection.execute(text(sql))
                    keys = tuple(str(key) for key in cursor.keys())
                    rows = cursor.fetchmany(self._settings.max_rows + 1)
                    column_metadata = self._column_metadata(cursor, keys)
                finally:
                    transaction.rollback()
            truncated = len(rows) > self._settings.max_rows
            bounded_rows = [tuple(row) for row in rows[:self._settings.max_rows]]
            dataframe = pd.DataFrame.from_records(bounded_rows, columns=list(keys))
            elapsed = max(0.0, (self._clock() - started) * 1000.0)
            plan = decision.plan or self._plans.estimate(sql)
            metadata = ExecutionMetadata(
                columns=column_metadata,
                statement_timeout_ms=self._settings.statement_timeout_ms,
                lock_timeout_ms=self._settings.lock_timeout_ms,
                truncated=truncated,
            )
            logger.info("Read-only SQL execution completed", extra={
                "event": "sql_execution_completed", "sql_sha256": sql_hash,
                "execution_time_ms": elapsed, "rows_returned": len(dataframe),
                "truncated": truncated,
            })
            return SqlExecutionResult(dataframe=dataframe, execution_time_ms=elapsed,
                                      rows_returned=len(dataframe), explain_plan=plan,
                                      metadata=metadata)
        except ExecutionRejectedError:
            raise
        except Exception as exc:
            elapsed = max(0.0, (self._clock() - started) * 1000.0)
            mapped = self._map_error(exc)
            logger.warning("Read-only SQL execution failed", extra={
                "event": "sql_execution_failed", "sql_sha256": sql_hash,
                "execution_time_ms": elapsed, "error_type": type(mapped).__name__,
            })
            raise mapped from exc

    @staticmethod
    def _approved_sql(decision: GuardrailDecision) -> str:
        if not decision.allowed or not decision.executable_sql:
            raise ExecutionRejectedError("SQL was not approved by guardrails")
        return decision.executable_sql

    @staticmethod
    def _column_metadata(cursor: Any, keys: tuple[str, ...]) -> tuple[ColumnMetadata, ...]:
        description = getattr(getattr(cursor, "cursor", None), "description", None) or ()
        types = {str(item[0]): str(item[1]) if len(item) > 1 and item[1] is not None else None
                 for item in description}
        return tuple(ColumnMetadata(name=key, data_type=types.get(key)) for key in keys)

    @staticmethod
    def _map_error(exc: Exception) -> Exception:
        if isinstance(exc, QueryPlanError):
            return ExecutionDatabaseError("Execution completed but explain plan was unavailable")
        if isinstance(exc, ProgrammingError):
            return ExecutionQueryError("Database rejected the SQL query")
        if isinstance(exc, OperationalError):
            if SqlAlchemyReadOnlyExecutor._is_timeout(exc):
                return ExecutionTimeoutError("SQL execution exceeded its configured timeout")
            return ExecutionConnectionError("Target database connection failed")
        if isinstance(exc, DBAPIError):
            if SqlAlchemyReadOnlyExecutor._is_timeout(exc):
                return ExecutionTimeoutError("SQL execution exceeded its configured timeout")
            return ExecutionDatabaseError("Target database could not execute the query")
        if isinstance(exc, SQLAlchemyError):
            return ExecutionDatabaseError("Target database execution failed")
        return ExecutionDatabaseError("Unexpected database execution failure")

    @staticmethod
    def _is_timeout(exc: DBAPIError) -> bool:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        return sqlstate in {"57014", "55P03"}
