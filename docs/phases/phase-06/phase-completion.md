# Phase 6 Completion — Read-only SQL Execution Engine

Status: **Complete**

## Delivered

- Application-level `QueryExecutor` interface and immutable execution DTOs.
- Guardrail-gated SQLAlchemy PostgreSQL executor; raw or rejected SQL cannot reach a connection.
- Explicit `SET TRANSACTION READ ONLY` on every execution transaction.
- Transaction-local statement and lock timeouts from validated environment settings.
- Unconditional rollback on successful and failed execution.
- Bounded `fetchmany(max_rows + 1)` result collection with explicit truncation metadata.
- Pandas DataFrame output, execution time in milliseconds, rows returned, explain plan, and
  column/result metadata.
- Reuse of the approved Phase 5 explain plan; fallback plan estimation only when absent.
- Driver-independent SQLAlchemy Row materialization and cursor metadata capture before rollback.
- Safe exception hierarchy for rejected SQL, query errors, timeouts, connection failures, and
  general database failures.
- PostgreSQL SQLSTATE timeout/cancellation and lock-timeout recognition.
- Structured success/failure logging with SQL SHA-256, elapsed time, row count, and error class;
  raw SQL and result values are excluded.
- Environment configuration for statement timeout, lock timeout, and maximum result rows.

## Reuse audit

Phase 5's `GuardrailDecision`, rewritten `executable_sql`, `QueryPlanEstimate`, and plan-estimator
port were reused directly. Phase 2's target SQLAlchemy engine approach and structured logging were
also reused. No second SQL parser, guardrail implementation, or duplicate EXPLAIN model was added.

## Execution sequence

1. Require an allowed guardrail decision containing executable SQL.
2. Open a target PostgreSQL connection and begin a transaction.
3. Set the transaction read-only.
4. Set transaction-local statement and lock timeouts.
5. Execute the approved SQL once.
6. Fetch at most `max_rows + 1`, capture columns, and roll back unconditionally.
7. Build a bounded DataFrame and truncation metadata.
8. Reuse the guardrail plan or obtain a plan through the existing estimator.
9. Return the typed result and record sanitized operational metrics.

## Security and reliability decisions

- The executor accepts `GuardrailDecision`, not a free-form SQL string.
- Database read-only permissions remain mandatory defense in depth; transaction mode is an
  additional control rather than a replacement for least-privilege credentials.
- Results are bounded before DataFrame construction to prevent unbounded application memory use.
- SQL text, row values, and raw database messages are never included in operational logs or safe
  outward-facing exceptions.
- No commit path exists in the executor.
- A plan failure is normalized even if row retrieval succeeded; the data transaction has already
  been rolled back safely.

## Verification

Executed from `backend/`:

```text
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Result: **65 tests passed**.

New coverage verifies DataFrame records, elapsed time, row count, column types, existing/fallback
plans, exact transaction statements, success/error rollback, result truncation, rejection before
connection, ProgrammingError sanitization, timeout SQLSTATE mapping, connection errors, safe logs,
and settings bounds. All previous phase tests remain green.

## Environment note

Local tests used installed Pandas 2.3.1 and SQLAlchemy 2.0.41. `psycopg` and a live PostgreSQL
server are not configured locally, so PostgreSQL transaction/timeout behavior was verified with
deterministic SQLAlchemy-compatible test doubles. Live driver integration remains a production
hardening gate.

## Next approval gate

Phase 7 will implement hallucination detection and confidence scoring, including back translation,
question/SQL similarity, result/aggregate/join/date validation, multi-query agreement, weighted
probability, explanations, breakdowns, and warnings. No Phase 7 code has been generated.
