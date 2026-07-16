# Delivery Roadmap

Each phase starts with a repository reuse audit, ends with tests and a dedicated `phase-completion.md`, and requires approval before the next phase begins.

## Phase 1 — Architecture and contracts ✅

- Complete system architecture, dependency rules, responsibilities, database/API/data-flow design, and diagrams.
- Define phase boundaries and acceptance criteria.
- Deliverable: `docs/phases/phase-01/phase-completion.md`.

## Phase 2 — Foundation and database layer ✅

- Backend scaffold, typed settings, structured logging, exception taxonomy, dependency injection.
- SQLAlchemy engine/session manager, application metadata models, repositories, unit of work.
- Target PostgreSQL connection registry and automatic schema extraction for tables, columns, keys, relationships, indexes, and bounded sample values.
- Unit and integration tests.

## Phase 3 — Schema retrieval and prompt system ✅

- Schema normalization, embeddings, FAISS-backed relevant-table retrieval.
- Versioned dynamic prompts containing schema, relationships, business rules, samples, few-shot examples, and output contract.
- Unit tests with deterministic adapters.

## Phase 4 — Groq integration ✅

- Multi-model Groq adapter, typed structured output, retries, rate-limit handling, and streaming.
- Keep provider concerns isolated; no business rules in the adapter.
- Contract and unit tests.

## Phase 5 — SQL validation and guardrails ✅

- AST-based PostgreSQL parser and syntax/schema validation.
- Block mutations/DDL, nested queries, multiple statements, and unsafe functions.
- Configurable LIMIT injection, EXPLAIN cost policy, structured errors, and security audit logging.
- Adversarial unit tests.

## Phase 6 — Read-only execution engine ✅

- Isolated read-only transaction, statement timeout, automatic rollback.
- DataFrame results, timing, row count, plan, and result metadata.
- Normalized database errors and PostgreSQL integration tests.

## Phase 7 — Hallucination and confidence engines ✅

- Back translation, question/SQL similarity, result/aggregate/join/date validation, and multi-query verification.
- Weighted hallucination probability with evidence-based explanation.
- Confidence score, component breakdown, warnings, and configurable calibration.
- Unit and evaluation tests.

## Phase 8 — Application orchestration and FastAPI ✅

- Text-to-SQL use-case orchestration and dependency composition.
- Query, schema, history, feedback, health, and optional streaming endpoints.
- Authentication/authorization seams, request IDs, validation, error envelope, and API tests.

## Phase 9 — React dashboard ✅

- Question input, editable highlighted SQL, results grid, confidence meter, warnings, history, dark mode, and responsive layout.
- Generated typed API client, component tests, accessibility checks, and production build.

## Phase 10 — Production hardening and delivery ✅

- Docker images and Compose, migrations, observability, secrets guidance, CI quality gates, security and performance tests.
- Deployment/runbooks, evaluation baseline, and final acceptance report.
