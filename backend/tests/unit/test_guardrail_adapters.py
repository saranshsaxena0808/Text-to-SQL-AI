import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.domain.entities.guardrails import GuardrailDecision, GuardrailViolation
from app.infrastructure.guardrails.audit import LoggingGuardrailAuditSink
from app.infrastructure.guardrails.plan import PostgresQueryPlanEstimator


class FakeResult:
    def scalar_one(self):
        return [{"Plan": {"Total Cost": 125.5, "Plan Rows": 800}}]


class FakeTransaction:
    def __init__(self) -> None:
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class FakeConnection:
    def __init__(self) -> None:
        self.statements = []
        self.transaction = FakeTransaction()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def begin(self):
        return self.transaction

    def execute(self, statement):
        rendered = str(statement)
        self.statements.append(rendered)
        return FakeResult()


class FakePostgresEngine:
    def __init__(self) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.connection = FakeConnection()

    def connect(self):
        return self.connection


class GuardrailAdapterTests(unittest.TestCase):
    def test_plan_estimator_uses_read_only_explain_and_rolls_back(self) -> None:
        engine = FakePostgresEngine()
        estimate = PostgresQueryPlanEstimator(engine).estimate("SELECT * FROM users LIMIT 10")
        self.assertEqual(estimate.total_cost, 125.5)
        self.assertEqual(estimate.estimated_rows, 800)
        self.assertEqual(engine.connection.statements[0], "SET TRANSACTION READ ONLY")
        self.assertEqual(engine.connection.statements[1],
                         "EXPLAIN (FORMAT JSON) SELECT * FROM users LIMIT 10")
        self.assertTrue(engine.connection.transaction.rolled_back)

    def test_logging_sink_emits_sanitized_audit_fields(self) -> None:
        decision = GuardrailDecision(
            allowed=False, original_sql="DELETE FROM users WHERE id = 42",
            violations=(GuardrailViolation(code="STATEMENT_BLOCKED", message="blocked"),),
        )
        with self.assertLogs("app.infrastructure.guardrails.audit", level="WARNING") as captured:
            LoggingGuardrailAuditSink().record_blocked(
                decision, "DELETE FROM users WHERE id = '[REDACTED]'", uuid4()
            )
        record = captured.records[0]
        self.assertEqual(record.event, "guardrail_blocked")
        self.assertEqual(record.violation_codes, ["STATEMENT_BLOCKED"])
        self.assertEqual(len(record.sql_sha256), 64)
        self.assertNotIn("42", record.sanitized_sql)
