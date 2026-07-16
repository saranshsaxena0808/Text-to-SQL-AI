import unittest
from types import SimpleNamespace

import pandas as pd
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.config.settings import ExecutionSettings
from app.domain.entities.guardrails import GuardrailDecision, GuardrailViolation, QueryPlanEstimate
from app.domain.exceptions import (
    ExecutionConnectionError, ExecutionQueryError, ExecutionRejectedError, ExecutionTimeoutError,
)
from app.domain.ports.guardrails import QueryPlanEstimator
from app.infrastructure.execution.sqlalchemy_executor import SqlAlchemyReadOnlyExecutor


class PlanStub(QueryPlanEstimator):
    def __init__(self) -> None:
        self.queries = []
        self.plan = QueryPlanEstimate(total_cost=12.5, estimated_rows=2,
                                      plan={"Plan": {"Node Type": "Seq Scan"}})

    def estimate(self, sql):
        self.queries.append(sql)
        return self.plan


class FakeTransaction:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self):
        self.rollback_calls += 1


class FakeCursor:
    def __init__(self, rows, columns) -> None:
        self._rows = rows
        self._columns = columns
        self.fetch_size = None
        self.cursor = SimpleNamespace(description=[(name, data_type) for name, data_type in columns])

    def keys(self):
        return [name for name, _ in self._columns]

    def fetchmany(self, size):
        self.fetch_size = size
        return self._rows[:size]


class FakeConnection:
    def __init__(self, rows=None, columns=None, query_error=None) -> None:
        self.transaction = FakeTransaction()
        self.cursor = FakeCursor(rows or [], columns or [("id", "INTEGER")])
        self.statements = []
        self.query_error = query_error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def begin(self):
        return self.transaction

    def execute(self, statement):
        rendered = str(statement)
        self.statements.append(rendered)
        if rendered.startswith("SELECT") and self.query_error:
            raise self.query_error
        if rendered.startswith("SELECT"):
            return self.cursor
        return SimpleNamespace()


class FakeEngine:
    def __init__(self, connection) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.connection = connection
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connection


def approved(plan=None):
    return GuardrailDecision(allowed=True, original_sql="SELECT id, name FROM users",
                             executable_sql="SELECT id, name FROM users LIMIT 100", plan=plan)


class ExecutionEngineTests(unittest.TestCase):
    def executor(self, connection, plan=None, max_rows=100, times=None):
        times = iter(times or [1.0, 1.025])
        estimator = plan or PlanStub()
        executor = SqlAlchemyReadOnlyExecutor(
            FakeEngine(connection), ExecutionSettings(statement_timeout_ms=5000,
                                                      lock_timeout_ms=500, max_rows=max_rows),
            estimator, clock=lambda: next(times),
        )
        return executor, estimator

    def test_returns_dataframe_timing_rows_plan_and_metadata(self) -> None:
        connection = FakeConnection(rows=[(1, "Ada"), (2, "Linus")],
                                    columns=[("id", "INTEGER"), ("name", "TEXT")])
        executor, estimator = self.executor(connection)
        result = executor.execute(approved())
        self.assertIsInstance(result.dataframe, pd.DataFrame)
        self.assertEqual(result.dataframe.to_dict("records"),
                         [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Linus"}])
        self.assertAlmostEqual(result.execution_time_ms, 25.0)
        self.assertEqual(result.rows_returned, 2)
        self.assertEqual(result.explain_plan.total_cost, 12.5)
        self.assertEqual(estimator.queries, ["SELECT id, name FROM users LIMIT 100"])
        self.assertEqual(result.metadata.columns[1].data_type, "TEXT")
        self.assertFalse(result.metadata.truncated)

    def test_sets_read_only_timeouts_and_always_rolls_back(self) -> None:
        connection = FakeConnection(rows=[(1,)], columns=[("id", "INTEGER")])
        executor, _ = self.executor(connection)
        executor.execute(approved())
        self.assertEqual(connection.statements, [
            "SET TRANSACTION READ ONLY",
            "SET LOCAL statement_timeout = 5000",
            "SET LOCAL lock_timeout = 500",
            "SELECT id, name FROM users LIMIT 100",
        ])
        self.assertEqual(connection.transaction.rollback_calls, 1)

    def test_reuses_guardrail_explain_plan(self) -> None:
        connection = FakeConnection(rows=[(1,)])
        known_plan = QueryPlanEstimate(total_cost=2, estimated_rows=1, plan={"Plan": {}})
        executor, estimator = self.executor(connection)
        result = executor.execute(approved(known_plan))
        self.assertIs(result.explain_plan, known_plan)
        self.assertEqual(estimator.queries, [])

    def test_bounds_fetch_and_reports_truncation(self) -> None:
        connection = FakeConnection(rows=[(1,), (2,), (3,)], columns=[("id", "INTEGER")])
        executor, _ = self.executor(connection, max_rows=2)
        result = executor.execute(approved())
        self.assertEqual(connection.cursor.fetch_size, 3)
        self.assertEqual(result.rows_returned, 2)
        self.assertTrue(result.metadata.truncated)

    def test_rejects_unapproved_decision_without_connecting(self) -> None:
        connection = FakeConnection()
        engine = FakeEngine(connection)
        executor = SqlAlchemyReadOnlyExecutor(engine, ExecutionSettings(), PlanStub())
        blocked = GuardrailDecision(allowed=False, original_sql="DELETE FROM users",
                                    violations=(GuardrailViolation(code="blocked", message="blocked"),))
        with self.assertRaises(ExecutionRejectedError):
            executor.execute(blocked)
        self.assertEqual(engine.connect_calls, 0)

    def test_query_error_is_normalized_and_transaction_rolls_back(self) -> None:
        original = Exception("secret database detail")
        error = ProgrammingError("SELECT secret", {}, original)
        connection = FakeConnection(query_error=error)
        executor, _ = self.executor(connection, times=[1.0, 1.01])
        with self.assertRaisesRegex(ExecutionQueryError, "Database rejected") as captured:
            executor.execute(approved())
        self.assertNotIn("secret", str(captured.exception))
        self.assertEqual(connection.transaction.rollback_calls, 1)

    def test_timeout_sqlstate_is_normalized(self) -> None:
        original = SimpleNamespace(sqlstate="57014")
        mapped = SqlAlchemyReadOnlyExecutor._map_error(OperationalError("sql", {}, original))
        self.assertIsInstance(mapped, ExecutionTimeoutError)

    def test_non_timeout_operational_error_is_connection_error(self) -> None:
        mapped = SqlAlchemyReadOnlyExecutor._map_error(
            OperationalError("sql", {}, SimpleNamespace(sqlstate="08006"))
        )
        self.assertIsInstance(mapped, ExecutionConnectionError)

    def test_logs_hash_and_metrics_without_sql_text(self) -> None:
        connection = FakeConnection(rows=[(1,)])
        executor, _ = self.executor(connection)
        with self.assertLogs("app.infrastructure.execution.sqlalchemy_executor", "INFO") as captured:
            executor.execute(approved())
        record = captured.records[0]
        self.assertEqual(record.event, "sql_execution_completed")
        self.assertEqual(len(record.sql_sha256), 64)
        self.assertFalse(hasattr(record, "sql"))
