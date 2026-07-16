from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.application.dto.query import EditedSqlCommand, QueryCommand, QueryOutcome
from app.bootstrap.container import ApplicationContainer
from app.presentation.api.dependencies import Identity, get_container, get_identity
from app.presentation.api.schemas import (
    DataSourceCreateRequest, DataSourceResponse, FeedbackRequest, FeedbackResponse,
    HealthResponse, HistoryPageResponse, QueryHistoryResponse, QueryRequest, QueryResponse,
    EditedSqlRequest,
)
from app.domain.entities.schema import SchemaSnapshot


router = APIRouter(prefix="/api/v1")


def _query_response(outcome: QueryOutcome) -> QueryResponse:
    return QueryResponse(
        query_run_id=outcome.query_run_id, status=outcome.status,
        generated_sql=outcome.generated_sql, explanation=outcome.explanation,
        rows=list(outcome.rows), columns=list(outcome.columns),
        execution_time_ms=outcome.execution_time_ms,
        confidence=(outcome.confidence.model_dump(mode="json") if outcome.confidence else None),
        hallucination=(outcome.hallucination.model_dump(mode="json") if outcome.hallucination else None),
        warnings=list(outcome.warnings),
        violations=[item.model_dump(mode="json") for item in outcome.violations],
        clarification_question=outcome.clarification_question,
    )


def _history_response(item) -> QueryHistoryResponse:
    return QueryHistoryResponse(id=item.id, data_source_id=item.data_source_id,
                                question=item.question, generated_sql=item.generated_sql_redacted,
                                status=item.status, model=item.model, confidence=item.confidence,
                                warnings=list(item.warnings), timings=item.timings,
                                created_at=item.created_at)


@router.post("/queries", response_model=QueryResponse)
def run_query(payload: QueryRequest, identity: Identity = Depends(get_identity),
              container: ApplicationContainer = Depends(get_container)) -> QueryResponse:
    return _query_response(container.queries.execute(QueryCommand(
        tenant_id=identity.tenant_id, user_id=identity.user_id,
        data_source_id=payload.data_source_id, question=payload.question, model=payload.model,
    )))


@router.post("/queries/{query_run_id}/execute", response_model=QueryResponse)
def execute_edited_sql(query_run_id: UUID, payload: EditedSqlRequest,
                       identity: Identity = Depends(get_identity),
                       container: ApplicationContainer = Depends(get_container)) -> QueryResponse:
    existing = container.history.get(identity.tenant_id, query_run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Query run was not found")
    return _query_response(container.queries.execute_edited(EditedSqlCommand(
        tenant_id=identity.tenant_id, user_id=identity.user_id,
        data_source_id=existing.data_source_id, query_run_id=query_run_id,
        question=existing.question, sql=payload.sql,
    )))


@router.get("/queries", response_model=HistoryPageResponse)
def list_history(limit: int = Query(default=50, ge=1, le=200),
                 offset: int = Query(default=0, ge=0),
                 identity: Identity = Depends(get_identity),
                 container: ApplicationContainer = Depends(get_container)) -> HistoryPageResponse:
    items = container.history.list(identity.tenant_id, limit, offset)
    return HistoryPageResponse(items=[_history_response(item) for item in items],
                               limit=limit, offset=offset)


@router.get("/queries/{query_run_id}", response_model=QueryHistoryResponse)
def get_history(query_run_id: UUID, identity: Identity = Depends(get_identity),
                container: ApplicationContainer = Depends(get_container)) -> QueryHistoryResponse:
    item = container.history.get(identity.tenant_id, query_run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Query run was not found")
    return _history_response(item)


@router.post("/data-sources", response_model=DataSourceResponse, status_code=201)
def create_data_source(payload: DataSourceCreateRequest,
                       identity: Identity = Depends(get_identity),
                       container: ApplicationContainer = Depends(get_container)) -> DataSourceResponse:
    item = container.data_sources.create(identity.tenant_id, payload.name,
                                         payload.secret_ref, payload.options)
    return DataSourceResponse(id=item.id, name=item.name, status=item.status,
                              created_at=item.created_at)


@router.get("/data-sources", response_model=list[DataSourceResponse])
def list_data_sources(identity: Identity = Depends(get_identity),
                      container: ApplicationContainer = Depends(get_container)):
    return [DataSourceResponse(id=item.id, name=item.name, status=item.status,
                               created_at=item.created_at)
            for item in container.data_sources.list(identity.tenant_id)]


@router.post("/data-sources/{data_source_id}/schema/refresh", response_model=SchemaSnapshot)
def refresh_schema(data_source_id: UUID, identity: Identity = Depends(get_identity),
                   container: ApplicationContainer = Depends(get_container)):
    return container.schemas.refresh(identity.tenant_id, data_source_id)


@router.get("/data-sources/{data_source_id}/schema", response_model=SchemaSnapshot)
def get_schema(data_source_id: UUID, identity: Identity = Depends(get_identity),
               container: ApplicationContainer = Depends(get_container)):
    return container.schemas.get(identity.tenant_id, data_source_id)


@router.post("/queries/{query_run_id}/feedback", response_model=FeedbackResponse, status_code=201)
def create_feedback(query_run_id: UUID, payload: FeedbackRequest,
                    identity: Identity = Depends(get_identity),
                    container: ApplicationContainer = Depends(get_container)) -> FeedbackResponse:
    item = container.feedback.create(identity.tenant_id, identity.user_id, query_run_id,
                                     payload.rating, payload.correction_sql, payload.comment)
    return FeedbackResponse(id=item.id, query_run_id=item.query_run_id,
                            rating=item.rating, created_at=item.created_at)


@router.get("/health/live", response_model=HealthResponse, include_in_schema=False)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, include_in_schema=False)
def readiness(container: ApplicationContainer = Depends(get_container)) -> HealthResponse:
    checks = container.readiness.check()
    if not checks or not all(checks.values()):
        raise HTTPException(status_code=503, detail="Application is not ready")
    return HealthResponse(status="ok", checks=checks)
