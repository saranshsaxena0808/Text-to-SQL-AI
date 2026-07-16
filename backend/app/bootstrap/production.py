from pathlib import Path

from app.application.interfaces.runtime import ReadinessProbe
from app.application.services import (
    ConfidenceEngine, DataSourceService, DynamicPromptBuilder, FeedbackService,
    HallucinationEngine, HistoryService, RunTextToSql, SchemaApplicationService,
    SchemaRetrievalService,
)
from app.application.services.hallucination_checks import (
    AggregateValidationCheck, BackTranslationCheck, DateValidationCheck, JoinValidationCheck,
    MultiQueryVerificationCheck, QuestionSimilarityCheck, ResultValidationCheck, SQLSimilarityCheck,
)
from app.bootstrap.container import ApplicationContainer
from app.config import get_settings
from app.infrastructure.guardrails import FileGuardrailPolicyLoader, SqlGlotPostgresParser
from app.infrastructure.llm import GroqLLMGateway
from app.infrastructure.persistence.sqlalchemy import ConnectionManager, SqlAlchemyUnitOfWork
from app.infrastructure.prompts import FilePromptTemplateRepository
from app.infrastructure.retrieval import FaissVectorIndex, SentenceTransformerEmbeddingProvider
from app.infrastructure.schema import SqlAlchemySchemaExtractor
from app.infrastructure.target_database import (
    EnvironmentSecretResolver, ProductionTargetRuntimeFactory, ProductionTargetSchemaGateway,
    TargetEngineRegistry,
)
from app.infrastructure.validation import (
    EmbeddingCosineSimilarity, RuleBasedBackTranslator, SqlGlotStructuralSimilarity,
    ValidationPolicyLoader,
)


class ProductionReadinessProbe(ReadinessProbe):
    def __init__(self, database: ConnectionManager, groq_configured: bool) -> None:
        self._database, self._groq_configured = database, groq_configured

    def check(self) -> dict[str, bool]:
        try:
            database = self._database.healthcheck()
        except Exception:
            database = False
        return {"control_database": database, "groq_configured": self._groq_configured}


def build_production_container() -> ApplicationContainer:
    settings = get_settings()
    backend_root = Path(__file__).resolve().parents[2]
    resolve_path = lambda value: (backend_root / value).resolve() if not Path(value).is_absolute() else Path(value)
    database = ConnectionManager(settings.database)
    uow_factory = lambda: SqlAlchemyUnitOfWork(database)
    embeddings = SentenceTransformerEmbeddingProvider(
        settings.retrieval.model_name, settings.retrieval.embedding_dimension)
    retrieval = SchemaRetrievalService(
        embeddings, FaissVectorIndex(settings.retrieval.embedding_dimension),
        settings.retrieval.top_k, settings.retrieval.max_tables)
    prompts = DynamicPromptBuilder(
        FilePromptTemplateRepository(resolve_path(settings.prompt.template_root)),
        settings.prompt.sample_value_limit)
    parser = SqlGlotPostgresParser()
    semantic = EmbeddingCosineSimilarity(embeddings)
    structural = SqlGlotStructuralSimilarity()
    hall_policy = ValidationPolicyLoader.hallucination(
        resolve_path(settings.validation.hallucination_policy_path))
    confidence_policy = ValidationPolicyLoader.confidence(
        resolve_path(settings.validation.confidence_policy_path))
    checks = [
        BackTranslationCheck(RuleBasedBackTranslator(parser), semantic),
        QuestionSimilarityCheck(semantic), SQLSimilarityCheck(structural),
        ResultValidationCheck(hall_policy.empty_result_risk), AggregateValidationCheck(),
        JoinValidationCheck(), DateValidationCheck(), MultiQueryVerificationCheck(structural),
    ]
    hallucination = HallucinationEngine(checks, hall_policy)
    confidence = ConfidenceEngine(confidence_policy)
    registry = TargetEngineRegistry(settings.database.target_engine_cache_size,
                                    settings.execution.statement_timeout_ms)
    secrets = EnvironmentSecretResolver()
    guardrail_policy = FileGuardrailPolicyLoader(resolve_path(settings.guardrails.policy_path)).load()
    runtimes = ProductionTargetRuntimeFactory(uow_factory, registry, secrets,
                                              guardrail_policy, settings.execution)
    schema_gateway = ProductionTargetSchemaGateway(
        registry, secrets, SqlAlchemySchemaExtractor(settings.database.sample_value_limit))
    queries = RunTextToSql(
        uow_factory, retrieval, prompts, GroqLLMGateway(settings.groq), parser,
        runtimes, hallucination, confidence, settings.prompt.default_name,
        settings.prompt.default_version,
    )
    return ApplicationContainer(
        queries=queries, data_sources=DataSourceService(uow_factory),
        schemas=SchemaApplicationService(uow_factory, schema_gateway),
        history=HistoryService(uow_factory), feedback=FeedbackService(uow_factory),
        readiness=ProductionReadinessProbe(
            database, bool(settings.groq.api_key.get_secret_value())),
        shutdown=lambda: (registry.dispose_all(), database.dispose()),
    )
