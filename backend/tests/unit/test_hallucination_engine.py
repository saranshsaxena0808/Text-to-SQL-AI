import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from app.application.dto.execution import ExecutionMetadata, SqlExecutionResult
from app.application.dto.validation import HallucinationContext
from app.application.interfaces.validation import HallucinationCheck
from app.application.services.hallucination_checks import (
    AggregateValidationCheck, BackTranslationCheck, DateValidationCheck, JoinValidationCheck,
    MultiQueryVerificationCheck, QuestionSimilarityCheck, ResultValidationCheck, SQLSimilarityCheck,
)
from app.application.services.hallucination_service import HallucinationEngine
from app.domain.entities.guardrails import QueryPlanEstimate
from app.domain.entities.hallucination import HallucinationPolicy, ValidationEvidence
from app.domain.entities.schema import (
    ColumnSchema, NamespaceSchema, RelationshipSchema, SchemaSnapshot, TableSchema,
)
from app.domain.ports.validation import BackTranslator, SemanticSimilarity, SqlSimilarity
from app.infrastructure.guardrails.parser import SqlGlotPostgresParser


class FixedSemanticSimilarity(SemanticSimilarity):
    def __init__(self, score=0.8) -> None:
        self.score = score

    def compare(self, left, right):
        return self.score


class FixedSqlSimilarity(SqlSimilarity):
    def __init__(self, score=0.75) -> None:
        self.score = score

    def compare(self, left_sql, right_sql):
        return self.score


class FixedTranslator(BackTranslator):
    def translate(self, sql):
        return "total order amount by customer"


def schema() -> SchemaSnapshot:
    customers = TableSchema(name="customers", columns=(
        ColumnSchema(name="id", data_type="INTEGER", nullable=False),
    ), primary_key=("id",))
    orders = TableSchema(name="orders", columns=(
        ColumnSchema(name="id", data_type="INTEGER", nullable=False),
        ColumnSchema(name="customer_id", data_type="INTEGER", nullable=False),
        ColumnSchema(name="amount", data_type="NUMERIC", nullable=False),
        ColumnSchema(name="created_at", data_type="TIMESTAMP", nullable=False),
    ), relationships=(RelationshipSchema(from_columns=("customer_id",), target_schema="public",
                                         target_table="customers", target_columns=("id",)),))
    isolated = TableSchema(name="audit", columns=(
        ColumnSchema(name="id", data_type="INTEGER", nullable=False),))
    return SchemaSnapshot(data_source_id=uuid4(), captured_at=datetime.now(timezone.utc),
                          dialect="postgresql", checksum="v1",
                          schemas=(NamespaceSchema(name="public",
                                                   tables=(customers, orders, isolated)),))


def execution(frame=None) -> SqlExecutionResult:
    frame = frame if frame is not None else pd.DataFrame([{"total": 42}])
    return SqlExecutionResult(
        dataframe=frame, execution_time_ms=2, rows_returned=len(frame),
        explain_plan=QueryPlanEstimate(total_cost=1, estimated_rows=len(frame), plan={}),
        metadata=ExecutionMetadata(columns=(), statement_timeout_ms=1000,
                                   lock_timeout_ms=100, truncated=False),
    )


def context(sql="SELECT SUM(amount) FROM orders WHERE created_at >= CURRENT_DATE",
            question="What is the total order amount this year?", candidates=()):
    return HallucinationContext(
        question=question, sql=sql, explanation="Calculates total order amount for the date range.",
        analysis=SqlGlotPostgresParser().analyze(sql), schema=schema(),
        execution=execution(), execution_succeeded=True, candidate_sql=candidates,
    )


class HallucinationCheckTests(unittest.TestCase):
    def test_back_translation_and_question_similarity(self) -> None:
        back = BackTranslationCheck(FixedTranslator(), FixedSemanticSimilarity(0.8)).evaluate(context())
        question = QuestionSimilarityCheck(FixedSemanticSimilarity(0.7)).evaluate(context())
        self.assertAlmostEqual(back.risk, 0.2)
        self.assertAlmostEqual(question.risk, 0.3)
        self.assertIn("back_translation", back.details)

    def test_sql_similarity_and_multi_query_verification(self) -> None:
        candidate = "SELECT SUM(amount) FROM orders"
        item = context(candidates=(candidate,))
        sql = SQLSimilarityCheck(FixedSqlSimilarity(0.75)).evaluate(item)
        multi = MultiQueryVerificationCheck(FixedSqlSimilarity(0.75)).evaluate(item)
        self.assertEqual(sql.risk, 0.25)
        self.assertEqual(multi.risk, 0.25)
        self.assertTrue(sql.available)

    def test_similarity_checks_report_unavailable_without_candidates(self) -> None:
        self.assertFalse(SQLSimilarityCheck(FixedSqlSimilarity()).evaluate(context()).available)
        self.assertFalse(MultiQueryVerificationCheck(FixedSqlSimilarity()).evaluate(context()).available)

    def test_result_validation_handles_failure_empty_and_invalid_numeric(self) -> None:
        failed = replace(context(), execution_succeeded=False, execution=None)
        empty = replace(context(), execution=execution(pd.DataFrame()))
        invalid = replace(context(), execution=execution(pd.DataFrame({"value": [float("inf")]})))
        check = ResultValidationCheck(empty_result_risk=0.3)
        self.assertEqual(check.evaluate(failed).risk, 1)
        self.assertEqual(check.evaluate(empty).risk, 0.3)
        self.assertEqual(check.evaluate(invalid).risk, 1)

    def test_aggregate_validation_detects_missing_aggregate(self) -> None:
        item = context(sql="SELECT amount FROM orders", question="What is the total amount?")
        self.assertEqual(AggregateValidationCheck().evaluate(item).risk, 0.9)
        self.assertEqual(AggregateValidationCheck().evaluate(context()).risk, 0)

    def test_join_validation_accepts_relationship_and_rejects_disconnected_tables(self) -> None:
        valid = context(sql=("SELECT o.id FROM orders o JOIN customers c "
                             "ON o.customer_id = c.id"), question="orders and customers")
        mixed_qualification = context(sql=("SELECT o.id FROM public.orders o JOIN customers c "
                                           "ON o.customer_id = c.id"),
                                      question="orders and customers")
        invalid = context(sql="SELECT o.id FROM orders o JOIN audit a ON o.id = a.id",
                          question="orders and audit")
        self.assertEqual(JoinValidationCheck().evaluate(valid).risk, 0)
        self.assertEqual(JoinValidationCheck().evaluate(mixed_qualification).risk, 0)
        self.assertEqual(JoinValidationCheck().evaluate(invalid).risk, 0.9)

    def test_date_validation_detects_missing_temporal_filter(self) -> None:
        missing = context(sql="SELECT * FROM orders", question="orders this month")
        self.assertEqual(DateValidationCheck().evaluate(missing).risk, 0.85)
        self.assertEqual(DateValidationCheck().evaluate(context()).risk, 0)


class StaticCheck(HallucinationCheck):
    def __init__(self, name, risk, available=True, fail=False) -> None:
        self._name, self.risk, self.available, self.fail = name, risk, available, fail

    @property
    def name(self):
        return self._name

    def evaluate(self, context):
        if self.fail:
            raise RuntimeError("internal secret")
        return ValidationEvidence(check=self.name, risk=self.risk, available=self.available,
                                  explanation=f"{self.name} evaluated")


class HallucinationEngineTests(unittest.TestCase):
    def test_renormalizes_available_weighted_evidence(self) -> None:
        checks = [StaticCheck("a", 0.2), StaticCheck("b", 0.8, available=False),
                  StaticCheck("c", 0.6)]
        policy = HallucinationPolicy(version="v1", weights={"a": 1, "b": 5, "c": 1})
        result = HallucinationEngine(checks, policy).evaluate(context())
        self.assertAlmostEqual(result.probability, 0.4)
        self.assertEqual(result.policy_version, "v1")

    def test_check_failure_is_contained_and_marked_unavailable(self) -> None:
        result = HallucinationEngine(
            [StaticCheck("safe", 0.1), StaticCheck("broken", 0, fail=True)],
            HallucinationPolicy(version="v1", weights={"safe": 1, "broken": 1}),
        ).evaluate(context())
        self.assertAlmostEqual(result.probability, 0.1)
        self.assertFalse(result.evidence[1].available)
        self.assertNotIn("secret", result.evidence[1].explanation)
