# Phase 8 Completion — Application Orchestration and FastAPI

Status: **Complete**

## Delivered

- Full `RunTextToSql` application use case orchestrating schema retrieval, prompt construction,
  Groq generation, AST guardrails, read-only execution, hallucination validation, confidence
  scoring, response construction, and sanitized history persistence.
- Explicit clarification, blocked, completed, and failed query lifecycle states.
- Edited-SQL execution through the same guardrail/execution/validation pipeline.
- Failure history containing safe error type only; raw provider/database messages are excluded.
- Data-source registration/listing, schema get/refresh, history get/list, and feedback services.
- Query-run and feedback domain entities, tenant-scoped repositories, SQLAlchemy models, and second
  Alembic migration.
- Concrete production composition root wiring every adapter and service from validated settings.
- `env://VARIABLE_NAME` target secret resolver; plaintext URLs are not stored in data-source rows.
- Per-target runtime factory for plan validation, guardrails, and execution.
- Multi-tenant-safe retrieval critical section preventing concurrent FAISS rebuild/search races.
- Versioned FastAPI `/api/v1` routes with Pydantic request/response contracts.
- Stable structured error envelope and centralized exception mapping.
- Request-ID propagation/generation and structured request latency logging without bodies.
- Tenant/user identity context dependency and tenant-scoped application calls.
- Liveness/readiness routes, OpenAPI generation, lifespan construction, and pool disposal on shutdown.
- Correct project-relative prompt/policy resolution independent of process working directory.
- Expanded `.gitignore` for Python, test, environment, frontend, and build artifacts.

## API routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/queries` | Run the complete Text-to-SQL workflow |
| POST | `/api/v1/queries/{query_run_id}/execute` | Execute edited SQL through all safety controls |
| GET | `/api/v1/queries` | Paginated tenant query history |
| GET | `/api/v1/queries/{query_run_id}` | Get one tenant-scoped query run |
| POST | `/api/v1/queries/{query_run_id}/feedback` | Record rating/correction/comment |
| POST | `/api/v1/data-sources` | Register a secret-referenced target |
| GET | `/api/v1/data-sources` | List tenant data sources without secrets |
| POST | `/api/v1/data-sources/{id}/schema/refresh` | Extract and persist target schema |
| GET | `/api/v1/data-sources/{id}/schema` | Return the latest typed schema snapshot |
| GET | `/api/v1/health/live` | Process liveness |
| GET | `/api/v1/health/ready` | Control DB and Groq configuration readiness |

## Reuse audit

All Phase 2–7 ports and implementations were reused: Unit of Work, schema snapshots, retrieval,
prompts, Groq, SQL parser, guardrails, execution, hallucination, confidence, logging, and settings.
No duplicate business logic was introduced in routers. Persistence was extended only for missing
history/feedback requirements.

## Architecture and security decisions

- Routers contain transport mapping only; use cases own orchestration and transaction decisions.
- API construction accepts an injected container for deterministic boundary tests.
- Default production container is created during lifespan, not module import.
- Query result rows are returned to the caller but are not persisted in history by default.
- Stored SQL is literal-redacted; data-source responses never include `secret_ref`.
- Every history/resource lookup is tenant-scoped.
- Missing or malformed identity headers return 401 rather than request-validation leakage.
- Edited SQL derives data source and question from tenant-scoped history instead of trusting client
  resource identifiers.
- Target connection secrets are resolved only at runtime from an environment reference.
- Lifespan shutdown disposes both target engine registry and control-plane engine.

## Authentication boundary

The current identity adapter accepts `X-Tenant-ID` and `X-User-ID` as **trusted upstream identity
headers**. It is suitable only behind an authenticating gateway that strips client-supplied values.
Direct public deployment is not approved. Replacing this adapter with verified OIDC/JWT claims (or
enforcing trusted-gateway authentication) is a Phase 10 production release gate.

## Verification

Executed from `backend/`:

```text
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Result: **96 tests passed**.

New coverage includes complete/blocked/clarification/failed orchestration, sanitized persistence,
tenant identity propagation, edited SQL scoping, query/history/schema/data-source/feedback/health
routes, secret omission, request IDs, structured validation errors, 401 behavior, readiness failure,
OpenAPI routes, query/feedback repository persistence, and cross-tenant history isolation. Every
previous phase test remains green.

## Environment and remaining integration gates

- API tests use FastAPI TestClient and injected application services; no live Groq call is made.
- `psycopg` and live PostgreSQL remain unavailable locally, so migrations and full production
  composition require integration verification in Phase 10.
- Streaming remains available in the Groq provider adapter, but a progressive end-to-end SSE query
  orchestration route was not added; the current REST workflow returns the fully validated result.
- Browser CORS policy will be configured with the React deployment in Phase 9/10.

## Next approval gate

Phase 9 will implement the React dashboard: question input, generated/editable highlighted SQL,
results grid, confidence meter, warnings, history, dark mode, responsive layout, generated API
types/client, accessibility, tests, and production build. No Phase 9 code has been generated.
