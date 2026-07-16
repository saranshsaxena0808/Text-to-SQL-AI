import time
from collections.abc import Callable
from datetime import datetime, timezone

from app.application.dto.query import EditedSqlCommand, QueryCommand, QueryOutcome
from app.application.dto.validation import HallucinationContext
from app.application.interfaces.runtime import TargetRuntimeFactory
from app.application.services.confidence_service import ConfidenceEngine
from app.application.services.hallucination_service import HallucinationEngine
from app.application.services.prompt_builder import DynamicPromptBuilder
from app.application.services.schema_retrieval import SchemaRetrievalService
from app.domain.entities.hallucination import ConfidenceSignals
from app.domain.entities.llm import GenerationOptions, GenerationRequest
from app.domain.entities.prompt import PromptContext
from app.domain.entities.query import QueryRun, QueryStatus
from app.domain.exceptions import DataSourceNotFoundError, ExecutionRejectedError
from app.domain.ports.guardrails import SqlParser
from app.domain.ports.llm import LLMGateway
from app.domain.ports.unit_of_work import UnitOfWork


class RunTextToSql:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], retrieval: SchemaRetrievalService,
                 prompts: DynamicPromptBuilder, llm: LLMGateway, parser: SqlParser,
                 runtimes: TargetRuntimeFactory, hallucination: HallucinationEngine,
                 confidence: ConfidenceEngine, template_name: str, template_version: str,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self._uow_factory, self._retrieval, self._prompts = uow_factory, retrieval, prompts
        self._llm, self._parser, self._runtimes = llm, parser, runtimes
        self._hallucination, self._confidence = hallucination, confidence
        self._template_name, self._template_version, self._clock = template_name, template_version, clock

    def execute(self, command: QueryCommand) -> QueryOutcome:
        started = self._clock()
        try:
            return self._execute(command, started)
        except Exception as exc:
            failed = self._run(command, QueryStatus.FAILED, None, command.model,
                               self._elapsed(started), evaluation={"error_type": type(exc).__name__})
            try:
                self._save(failed)
            except Exception:
                pass
            raise

    def _execute(self, command: QueryCommand, started: float) -> QueryOutcome:
        snapshot = self._snapshot(command.data_source_id, command.tenant_id)
        relevant = self._retrieval.retrieve(command.question, snapshot)
        prompt = self._prompts.build(PromptContext(question=command.question,
                                                   relevant_schema=relevant),
                                     self._template_name, self._template_version)
        llm_response = self._llm.generate(GenerationRequest(
            prompt=prompt, options=GenerationOptions(model=command.model)))
        generated = llm_response.result
        if generated.clarification_needed or not generated.sql:
            run = self._run(command, QueryStatus.CLARIFICATION_REQUIRED, None,
                            llm_response.model, self._elapsed(started), evaluation={})
            self._save(run)
            return QueryOutcome(query_run_id=run.id, status=run.status, generated_sql=None,
                                explanation=generated.explanation,
                                clarification_question=generated.clarification_question)
        return self._validate_execute(command, generated.sql, generated.explanation, snapshot,
                                      llm_response.model, started)

    def execute_edited(self, command: EditedSqlCommand) -> QueryOutcome:
        started = self._clock()
        snapshot = self._snapshot(command.data_source_id, command.tenant_id)
        base = QueryCommand(tenant_id=command.tenant_id, user_id=command.user_id,
                            data_source_id=command.data_source_id, question=command.question,
                            model="user-edited")
        return self._validate_execute(base, command.sql, "User-edited SQL.", snapshot,
                                      "user-edited", started)

    def _validate_execute(self, command: QueryCommand, sql: str, explanation: str,
                          snapshot, model: str, started: float) -> QueryOutcome:
        runtime = self._runtimes.create(command.data_source_id, command.tenant_id)
        decision = runtime.guardrails.evaluate(sql, snapshot)
        if not decision.allowed:
            warnings = tuple(violation.message for violation in decision.violations)
            run = self._run(command, QueryStatus.BLOCKED, self._parser.sanitize(sql), model,
                            self._elapsed(started), warnings=warnings,
                            evaluation={"violations": [item.model_dump(mode="json")
                                                       for item in decision.violations]})
            self._save(run)
            return QueryOutcome(query_run_id=run.id, status=run.status, generated_sql=sql,
                                explanation=explanation, warnings=warnings,
                                violations=decision.violations)
        execution = runtime.executor.execute(decision)
        analysis = self._parser.analyze(decision.executable_sql or sql)
        hall = self._hallucination.evaluate(HallucinationContext(
            question=command.question, sql=decision.executable_sql or sql,
            explanation=explanation, analysis=analysis, schema=snapshot,
            execution=execution, execution_succeeded=True,
        ))
        evidence = {item.check: item for item in hall.evidence}
        multi = evidence.get("multi_query_verification")
        question = evidence.get("question_similarity")
        confidence = self._confidence.calculate(ConfidenceSignals(
            syntax_score=1, schema_coverage=1, execution_success=1,
            hallucination_probability=hall.probability,
            multi_query_agreement=(1 - multi.risk if multi and multi.available else 0.5),
            explainability=(1 - question.risk if question and question.available else 0.5),
        ))
        run = self._run(command, QueryStatus.COMPLETED, self._parser.sanitize(sql), model,
                        self._elapsed(started), confidence.score, confidence.warnings,
                        {"hallucination": hall.model_dump(mode="json"),
                         "confidence": confidence.model_dump(mode="json")})
        self._save(run)
        rows = tuple(dict(row) for row in execution.dataframe.to_dict(orient="records"))
        return QueryOutcome(query_run_id=run.id, status=run.status,
                            generated_sql=decision.executable_sql, explanation=explanation,
                            rows=rows, columns=tuple(str(c) for c in execution.dataframe.columns),
                            execution_time_ms=execution.execution_time_ms,
                            confidence=confidence, hallucination=hall,
                            warnings=confidence.warnings)

    def _snapshot(self, data_source_id, tenant_id):
        with self._uow_factory() as uow:
            source = uow.data_sources.get(data_source_id, tenant_id)
            snapshot = uow.schema_snapshots.latest(data_source_id, tenant_id) if source else None
        if source is None or snapshot is None:
            raise DataSourceNotFoundError("Data source or schema snapshot was not found")
        return snapshot

    def _save(self, run: QueryRun) -> None:
        with self._uow_factory() as uow:
            uow.query_runs.add(run)
            uow.commit()

    def _run(self, command: QueryCommand, status: QueryStatus, sql: str | None, model: str,
             elapsed: float, confidence: float | None = None, warnings: tuple[str, ...] = (),
             evaluation: dict[str, object] | None = None) -> QueryRun:
        return QueryRun(tenant_id=command.tenant_id, user_id=command.user_id,
                        data_source_id=command.data_source_id, question=command.question,
                        generated_sql_redacted=sql, status=status, model=model,
                        prompt_version=self._template_version, confidence=confidence,
                        evaluation=evaluation or {}, timings={"total_ms": elapsed},
                        warnings=warnings, created_at=datetime.now(timezone.utc))

    def _elapsed(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000)
