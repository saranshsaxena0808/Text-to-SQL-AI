import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.application.services.guardrail_service import GuardrailEngine
from app.domain.entities.guardrails import GuardrailPolicy, QueryPlanEstimate
from app.domain.entities.schema import ColumnSchema, NamespaceSchema, SchemaSnapshot, TableSchema
from app.domain.exceptions import GuardrailConfigurationError, QueryPlanError
from app.domain.ports.guardrails import GuardrailAuditSink, QueryPlanEstimator
from app.infrastructure.guardrails.config import FileGuardrailPolicyLoader
from app.infrastructure.guardrails.parser import SqlGlotPostgresParser


class AuditSpy(GuardrailAuditSink):
    def __init__(self) -> None:
        self.events = []

    def record_blocked(self, decision, sanitized_sql, query_run_id=None):
        self.events.append((decision, sanitized_sql, query_run_id))


class PlanStub(QueryPlanEstimator):
    def __init__(self, cost=10.0, rows=100, error=False) -> None:
        self.cost, self.rows, self.error = cost, rows, error
        self.queries = []

    def estimate(self, sql):
        self.queries.append(sql)
        if self.error:
            raise QueryPlanError("failed")
        return QueryPlanEstimate(total_cost=self.cost, estimated_rows=self.rows,
                                 plan={"Plan": {"Total Cost": self.cost}})


def snapshot() -> SchemaSnapshot:
    users = TableSchema(name="users", columns=(
        ColumnSchema(name="id", data_type="INTEGER", nullable=False),
        ColumnSchema(name="email", data_type="TEXT", nullable=False),
    ), primary_key=("id",))
    orders = TableSchema(name="orders", columns=(
        ColumnSchema(name="id", data_type="INTEGER", nullable=False),
        ColumnSchema(name="amount", data_type="NUMERIC", nullable=False),
    ), primary_key=("id",))
    return SchemaSnapshot(data_source_id=uuid4(), captured_at=datetime.now(timezone.utc),
                          dialect="postgresql", checksum="schema",
                          schemas=(NamespaceSchema(name="public", tables=(users, orders)),))


class GuardrailEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = SqlGlotPostgresParser()
        self.audit = AuditSpy()
        self.plans = PlanStub()
        self.policy = GuardrailPolicy(version="test", default_limit=100,
                                      max_plan_cost=1000, max_estimated_rows=10000)
        self.engine = GuardrailEngine(self.parser, self.policy, self.audit, self.plans)

    def codes(self, sql, schema=None):
        return {item.code for item in self.engine.evaluate(sql, schema).violations}

    def test_injects_limit_and_accepts_safe_select(self) -> None:
        decision = self.engine.evaluate("SELECT id FROM public.users", snapshot())
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.injected_limit)
        self.assertEqual(decision.executable_sql, "SELECT id FROM public.users LIMIT 100")
        self.assertEqual(self.plans.queries, [decision.executable_sql])

    def test_preserves_limit_within_maximum(self) -> None:
        decision = self.engine.evaluate("SELECT * FROM users LIMIT 20", snapshot())
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.injected_limit)
        self.assertIn("LIMIT 20", decision.executable_sql)

    def test_clamps_limit_above_maximum(self) -> None:
        decision = self.engine.evaluate("SELECT * FROM users LIMIT 1000", snapshot())
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.injected_limit)
        self.assertIn("LIMIT 100", decision.executable_sql)

    def test_blocks_every_mutating_and_ddl_statement(self) -> None:
        queries = {
            "DELETE": "DELETE FROM users", "DROP": "DROP TABLE users",
            "UPDATE": "UPDATE users SET email = 'x'", "INSERT": "INSERT INTO users VALUES (1, 'x')",
            "ALTER": "ALTER TABLE users ADD COLUMN x INT", "CREATE": "CREATE TABLE x (id INT)",
            "MERGE": "MERGE INTO users USING other ON users.id = other.id WHEN MATCHED THEN DELETE",
            "TRUNCATETABLE": "TRUNCATE TABLE users",
        }
        for expected, sql in queries.items():
            with self.subTest(expected=expected):
                decision = self.engine.evaluate(sql)
                self.assertFalse(decision.allowed)
                self.assertIn("STATEMENT_BLOCKED", {v.code for v in decision.violations})

    def test_blocks_nested_query(self) -> None:
        self.assertIn("NESTED_QUERY_BLOCKED", self.codes(
            "SELECT * FROM users WHERE id IN (SELECT id FROM admins)"))

    def test_blocks_cte_as_nested_query(self) -> None:
        self.assertIn("NESTED_QUERY_BLOCKED", self.codes(
            "WITH active AS (SELECT * FROM users) SELECT * FROM active"))

    def test_blocks_multiple_statements(self) -> None:
        self.assertIn("MULTIPLE_STATEMENTS", self.codes("SELECT * FROM users; DROP TABLE users"))

    def test_blocks_locking_select_and_select_into(self) -> None:
        self.assertIn("LOCKING_CLAUSE_BLOCKED", self.codes("SELECT * FROM users FOR UPDATE"))
        self.assertIn("SELECT_INTO_BLOCKED", self.codes("SELECT * INTO copied FROM users"))

    def test_blocks_configured_function(self) -> None:
        self.assertIn("FUNCTION_BLOCKED", self.codes("SELECT pg_sleep(10)"))

    def test_blocks_unknown_table_and_column(self) -> None:
        self.assertIn("UNKNOWN_TABLE", self.codes("SELECT id FROM payments", snapshot()))
        self.assertIn("UNKNOWN_COLUMN", self.codes("SELECT password FROM users", snapshot()))

    def test_qualified_columns_resolve_against_exact_alias(self) -> None:
        accepted = self.engine.evaluate(
            "SELECT u.email, o.amount FROM users AS u JOIN orders AS o ON u.id = o.id", snapshot())
        rejected = self.engine.evaluate(
            "SELECT u.amount FROM users AS u JOIN orders AS o ON u.id = o.id", snapshot())
        self.assertTrue(accepted.allowed)
        self.assertIn("UNKNOWN_COLUMN", {v.code for v in rejected.violations})

    def test_blocks_select_callable_side_effects(self) -> None:
        for sql in ("SELECT set_config('search_path', 'evil', false)",
                    "SELECT nextval('orders_id_seq')", "SELECT pg_advisory_lock(1)"):
            with self.subTest(sql=sql):
                self.assertIn("FUNCTION_BLOCKED", self.codes(sql))

    def test_blocks_expensive_cost_and_rows(self) -> None:
        costly = GuardrailEngine(self.parser, self.policy, self.audit,
                                 PlanStub(cost=1001, rows=10001)).evaluate("SELECT * FROM users")
        self.assertEqual({v.code for v in costly.violations},
                         {"PLAN_COST_EXCEEDED", "PLAN_ROWS_EXCEEDED"})

    def test_fails_closed_when_plan_is_missing_or_errors(self) -> None:
        no_estimator = GuardrailEngine(self.parser, self.policy, self.audit).evaluate(
            "SELECT * FROM users")
        failed = GuardrailEngine(self.parser, self.policy, self.audit,
                                 PlanStub(error=True)).evaluate("SELECT * FROM users")
        self.assertEqual(no_estimator.violations[0].code, "PLAN_ESTIMATOR_MISSING")
        self.assertEqual(failed.violations[0].code, "PLAN_UNAVAILABLE")

    def test_parse_error_is_structured(self) -> None:
        self.assertIn("SQL_PARSE_ERROR", self.codes("SELECT * FROM"))

    def test_every_blocked_decision_is_audited_with_redacted_literals(self) -> None:
        run_id = uuid4()
        decision = self.engine.evaluate("UPDATE users SET email = 'secret@example.com' WHERE id = 42",
                                        query_run_id=run_id)
        self.assertFalse(decision.allowed)
        self.assertEqual(len(self.audit.events), 1)
        _, sanitized, recorded_id = self.audit.events[0]
        self.assertNotIn("secret@example.com", sanitized)
        self.assertNotIn("42", sanitized)
        self.assertEqual(recorded_id, run_id)


class GuardrailConfigTests(unittest.TestCase):
    def test_loads_yaml_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.yaml"
            path.write_text("version: v2\ndefault_limit: 25\nexplain_enabled: false\n", encoding="utf-8")
            policy = FileGuardrailPolicyLoader(path).load()
        self.assertEqual(policy.version, "v2")
        self.assertEqual(policy.default_limit, 25)

    def test_invalid_yaml_policy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.yaml"
            path.write_text("version: v1\ndefault_limit: 0\n", encoding="utf-8")
            with self.assertRaises(GuardrailConfigurationError):
                FileGuardrailPolicyLoader(path).load()
