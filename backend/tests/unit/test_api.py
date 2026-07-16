import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.dto.query import QueryOutcome
from app.bootstrap.container import ApplicationContainer
from app.domain.entities.data_source import DataSource, DataSourceStatus
from app.domain.entities.query import Feedback, QueryRun, QueryStatus
from app.presentation.api import create_app


TENANT = uuid4()
USER = uuid4()
SOURCE = uuid4()
RUN = uuid4()
HEADERS = {"X-Tenant-ID": str(TENANT), "X-User-ID": str(USER)}


class QueryStub:
    def __init__(self) -> None:
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return QueryOutcome(query_run_id=RUN, status=QueryStatus.COMPLETED,
                            generated_sql="SELECT 1 LIMIT 500", explanation="constant",
                            rows=({"value": 1},), columns=("value",), execution_time_ms=1.2)

    def execute_edited(self, command):
        self.commands.append(command)
        return QueryOutcome(query_run_id=uuid4(), status=QueryStatus.COMPLETED,
                            generated_sql=command.sql, explanation="edited")


class DataSourceStub:
    def __init__(self):
        self.item = DataSource(id=SOURCE, tenant_id=TENANT, name="warehouse",
                               secret_ref="env://WAREHOUSE_URL", status=DataSourceStatus.ACTIVE,
                               created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))

    def create(self, tenant_id, name, secret_ref, options):
        self.received = (tenant_id, name, secret_ref, options)
        return self.item

    def list(self, tenant_id):
        self.tenant_id = tenant_id
        return [self.item]


class HistoryStub:
    def __init__(self):
        self.item = QueryRun(id=RUN, tenant_id=TENANT, user_id=USER, data_source_id=SOURCE,
                             question="question", generated_sql_redacted="SELECT 1",
                             status=QueryStatus.COMPLETED, model="model", confidence=0.8,
                             warnings=(), created_at=datetime.now(timezone.utc))

    def get(self, tenant_id, query_run_id):
        return self.item if tenant_id == TENANT and query_run_id == RUN else None

    def list(self, tenant_id, limit, offset):
        self.pagination = (tenant_id, limit, offset)
        return [self.item]


class SchemaStub:
    def get(self, tenant_id, data_source_id):
        from app.domain.entities.schema import SchemaSnapshot
        return SchemaSnapshot(data_source_id=data_source_id, captured_at=datetime.now(timezone.utc),
                              dialect="postgresql", checksum="abc", schemas=())

    refresh = get


class FeedbackStub:
    def create(self, tenant_id, user_id, query_run_id, rating, correction_sql, comment):
        return Feedback(tenant_id=tenant_id, user_id=user_id, query_run_id=query_run_id,
                        rating=rating, correction_sql=correction_sql, comment=comment,
                        created_at=datetime.now(timezone.utc))


class ReadinessStub:
    def __init__(self, ready=True):
        self.ready = ready

    def check(self):
        return {"control_database": self.ready, "groq_configured": self.ready}


def container(ready=True):
    return ApplicationContainer(queries=QueryStub(), data_sources=DataSourceStub(),
                                schemas=SchemaStub(), history=HistoryStub(),
                                feedback=FeedbackStub(), readiness=ReadinessStub(ready))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.container = container()
        self.client_context = TestClient(create_app(self.container))
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_query_endpoint_propagates_identity_and_returns_result(self):
        response = self.client.post("/api/v1/queries", headers=HEADERS, json={
            "data_source_id": str(SOURCE), "question": "one", "model": "model"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"], [{"value": 1}])
        command = self.container.queries.commands[0]
        self.assertEqual(command.tenant_id, TENANT)
        self.assertEqual(response.headers["X-Request-ID"], response.json().get("request_id",
                                                                              response.headers["X-Request-ID"]))

    def test_validation_error_uses_stable_envelope_and_request_id(self):
        response = self.client.post("/api/v1/queries", headers={**HEADERS, "X-Request-ID": "req-123"},
                                    json={"data_source_id": str(SOURCE), "question": ""})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")
        self.assertEqual(response.json()["error"]["request_id"], "req-123")
        self.assertEqual(response.headers["X-Request-ID"], "req-123")

    def test_invalid_identity_is_unauthorized(self):
        response = self.client.get("/api/v1/queries", headers={"X-Tenant-ID": "bad",
                                                                "X-User-ID": str(USER)})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")
        missing = self.client.get("/api/v1/queries")
        self.assertEqual(missing.status_code, 401)

    def test_history_and_edited_sql_are_tenant_scoped(self):
        history = self.client.get("/api/v1/queries?limit=10&offset=2", headers=HEADERS)
        edited = self.client.post(f"/api/v1/queries/{RUN}/execute", headers=HEADERS,
                                  json={"sql": "SELECT 2"})
        self.assertEqual(history.status_code, 200)
        self.assertEqual(self.container.history.pagination, (TENANT, 10, 2))
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(self.container.queries.commands[-1].data_source_id, SOURCE)

    def test_data_source_response_never_exposes_secret_reference(self):
        response = self.client.post("/api/v1/data-sources", headers=HEADERS,
                                    json={"name": "warehouse", "secret_ref": "env://WAREHOUSE_URL"})
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("secret_ref", response.json())

    def test_schema_feedback_and_health_endpoints(self):
        schema = self.client.get(f"/api/v1/data-sources/{SOURCE}/schema", headers=HEADERS)
        feedback = self.client.post(f"/api/v1/queries/{RUN}/feedback", headers=HEADERS,
                                    json={"rating": 5, "comment": "good"})
        live = self.client.get("/api/v1/health/live")
        ready = self.client.get("/api/v1/health/ready")
        self.assertEqual(schema.json()["checksum"], "abc")
        self.assertEqual(feedback.status_code, 201)
        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)

    def test_readiness_fails_when_dependency_is_unhealthy(self):
        with TestClient(create_app(container(False))) as client:
            response = client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "NOT_READY")

    def test_openapi_contains_versioned_core_routes(self):
        document = self.client.get("/openapi.json").json()
        for path in ("/api/v1/queries", "/api/v1/queries/{query_run_id}",
                     "/api/v1/data-sources", "/api/v1/queries/{query_run_id}/feedback"):
            self.assertIn(path, document["paths"])

    def test_metrics_and_security_headers_are_exposed_without_sensitive_labels(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text2sql_http_requests_total", response.text)
        self.assertNotIn(str(TENANT), response.text)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_cors_allows_configured_frontend_origin(self):
        response = self.client.options("/api/v1/queries", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-tenant-id,x-user-id",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
