import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from app.application.dto.execution import ExecutionMetadata, SqlExecutionResult
from app.application.dto.query import QueryCommand
from app.application.services.query_service import RunTextToSql
from app.domain.entities.data_source import DataSource
from app.domain.entities.guardrails import GuardrailDecision, GuardrailViolation, QueryPlanEstimate
from app.domain.entities.hallucination import (
    ConfidenceAssessment, ConfidenceComponent, HallucinationAssessment, ValidationEvidence,
)
from app.domain.entities.llm import LLMResponse, SqlGenerationResult
from app.domain.entities.prompt import BuiltPrompt
from app.domain.entities.query import QueryStatus
from app.domain.entities.retrieval import RelevantSchema
from app.domain.entities.schema import NamespaceSchema, SchemaSnapshot
from app.infrastructure.guardrails.parser import SqlGlotPostgresParser


class MemoryStore:
    def __init__(self):
        self.tenant = uuid4()
        self.user = uuid4()
        self.source = DataSource(tenant_id=self.tenant, name="source", secret_ref="env://DB_URL",
                                 created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        self.snapshot = SchemaSnapshot(data_source_id=self.source.id,
                                       captured_at=datetime.now(timezone.utc), dialect="postgresql",
                                       checksum="schema", schemas=(NamespaceSchema(name="public", tables=()),))
        self.runs = []


class MemoryUow:
    def __init__(self, store):
        self.store = store
        self.data_sources = SimpleNamespace(
            get=lambda source_id, tenant_id: store.source
            if source_id == store.source.id and tenant_id == store.tenant else None)
        self.schema_snapshots = SimpleNamespace(
            latest=lambda source_id, tenant_id: store.snapshot
            if source_id == store.source.id and tenant_id == store.tenant else None)
        self.query_runs = SimpleNamespace(add=store.runs.append)
        self.feedback = SimpleNamespace()

    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def commit(self): return None
    def rollback(self): return None


class RetrievalStub:
    def retrieve(self, question, snapshot):
        return RelevantSchema(snapshot_checksum=snapshot.checksum, tables=())


class PromptStub:
    def build(self, context, name, version):
        return BuiltPrompt(template_name=name, template_version=version,
                           template_checksum="prompt", system="system", user=context.question)


class LlmStub:
    def __init__(self, result): self.result = result
    def generate(self, request): return LLMResponse(model=request.options.model, result=self.result)


class FailingLlmStub:
    def generate(self, request):
        raise RuntimeError("provider secret")


class GuardrailStub:
    def __init__(self, decision): self.decision = decision
    def evaluate(self, sql, schema): return self.decision


class ExecutorStub:
    def execute(self, decision):
        frame = pd.DataFrame([{"value": 1}])
        return SqlExecutionResult(
            dataframe=frame, execution_time_ms=3.5, rows_returned=1,
            explain_plan=QueryPlanEstimate(total_cost=1, estimated_rows=1, plan={}),
            metadata=ExecutionMetadata(columns=(), statement_timeout_ms=1000,
                                       lock_timeout_ms=100, truncated=False))


class RuntimeStub:
    def __init__(self, decision): self.decision = decision; self.calls = 0
    def create(self, source_id, tenant_id):
        self.calls += 1
        return SimpleNamespace(guardrails=GuardrailStub(self.decision), executor=ExecutorStub())


class HallucinationStub:
    def evaluate(self, context):
        return HallucinationAssessment(
            probability=0.1, explanation="low risk", policy_version="v1",
            evidence=(ValidationEvidence(check="question_similarity", risk=0.2,
                                         explanation="aligned"),
                      ValidationEvidence(check="multi_query_verification", risk=0,
                                         available=False, explanation="unavailable")))


class ConfidenceStub:
    def calculate(self, signals):
        return ConfidenceAssessment(
            score=0.85, policy_version="v1", warnings=(),
            breakdown=(ConfidenceComponent(name="syntax_score", raw_score=1,
                                           weight=1, contribution=1),))


def generated(sql="SELECT 1", clarification=False):
    return SqlGenerationResult(sql=None if clarification else sql, confidence=0.9,
                               explanation="explanation", tables=(), columns=(),
                               clarification_needed=clarification,
                               clarification_question="Which period?" if clarification else None)


class QueryOrchestrationTests(unittest.TestCase):
    def service(self, store, result, decision):
        runtimes = RuntimeStub(decision)
        values = iter([1.0, 1.01])
        service = RunTextToSql(
            lambda: MemoryUow(store), RetrievalStub(), PromptStub(), LlmStub(result),
            SqlGlotPostgresParser(), runtimes, HallucinationStub(), ConfidenceStub(),
            "text_to_sql", "v1", clock=lambda: next(values))
        return service, runtimes

    def command(self, store):
        return QueryCommand(tenant_id=store.tenant, user_id=store.user,
                            data_source_id=store.source.id, question="show one", model="model")

    def test_success_runs_pipeline_and_persists_sanitized_history(self):
        store = MemoryStore()
        decision = GuardrailDecision(allowed=True, original_sql="SELECT 1",
                                     executable_sql="SELECT 1 LIMIT 500")
        service, runtime = self.service(store, generated(), decision)
        outcome = service.execute(self.command(store))
        self.assertEqual(outcome.status, QueryStatus.COMPLETED)
        self.assertEqual(outcome.rows, ({"value": 1},))
        self.assertEqual(outcome.confidence.score, 0.85)
        self.assertEqual(runtime.calls, 1)
        self.assertEqual(store.runs[0].status, QueryStatus.COMPLETED)
        self.assertNotEqual(store.runs[0].generated_sql_redacted, "SELECT 1")
        self.assertIn("REDACTED", store.runs[0].generated_sql_redacted)

    def test_clarification_stops_before_runtime(self):
        store = MemoryStore()
        service, runtime = self.service(store, generated(clarification=True),
                                        GuardrailDecision(allowed=True, original_sql="SELECT 1",
                                                          executable_sql="SELECT 1"))
        outcome = service.execute(self.command(store))
        self.assertEqual(outcome.status, QueryStatus.CLARIFICATION_REQUIRED)
        self.assertEqual(outcome.clarification_question, "Which period?")
        self.assertEqual(runtime.calls, 0)
        self.assertEqual(store.runs[0].status, QueryStatus.CLARIFICATION_REQUIRED)

    def test_blocked_query_returns_violations_without_execution(self):
        store = MemoryStore()
        violation = GuardrailViolation(code="STATEMENT_BLOCKED", message="Only SELECT")
        decision = GuardrailDecision(allowed=False, original_sql="DELETE FROM users",
                                     violations=(violation,))
        service, _ = self.service(store, generated("DELETE FROM users"), decision)
        outcome = service.execute(self.command(store))
        self.assertEqual(outcome.status, QueryStatus.BLOCKED)
        self.assertEqual(outcome.violations[0].code, "STATEMENT_BLOCKED")
        self.assertEqual(store.runs[0].status, QueryStatus.BLOCKED)

    def test_failure_is_persisted_without_raw_error_details(self):
        store = MemoryStore()
        runtimes = RuntimeStub(GuardrailDecision(allowed=True, original_sql="SELECT 1",
                                                 executable_sql="SELECT 1"))
        times = iter([1.0, 1.01])
        service = RunTextToSql(
            lambda: MemoryUow(store), RetrievalStub(), PromptStub(), FailingLlmStub(),
            SqlGlotPostgresParser(), runtimes, HallucinationStub(), ConfidenceStub(),
            "text_to_sql", "v1", clock=lambda: next(times))
        with self.assertRaises(RuntimeError):
            service.execute(self.command(store))
        self.assertEqual(store.runs[0].status, QueryStatus.FAILED)
        self.assertEqual(store.runs[0].evaluation, {"error_type": "RuntimeError"})
        self.assertNotIn("secret", str(store.runs[0].evaluation))
