# Phase 5 Completion — SQL Validation and Guardrails

Status: **Complete**

## Delivered

- Provider-neutral SQL parser, plan estimator, and blocked-query audit ports.
- PostgreSQL-dialect SQLGlot AST parser and normalized `SqlAnalysis` contract.
- Single-statement and SELECT-only enforcement blocking DELETE, DROP, UPDATE, INSERT, ALTER,
  CREATE, MERGE, TRUNCATE, and every other non-SELECT root statement.
- Nested-query and CTE rejection, plus multi-statement detection.
- `SELECT INTO` and row-locking clause rejection.
- Configurable blocked-function policy covering file access, database links, delays, runtime
  configuration mutation, advisory locks, and sequence mutation.
- Schema validation for tables and columns, including exact alias-qualified column resolution.
- Automatic LIMIT injection and clamping through AST rewriting.
- PostgreSQL `EXPLAIN (FORMAT JSON)` cost/row estimator in an explicit read-only transaction with
  unconditional rollback.
- Fail-closed plan behavior and configurable cost/estimated-row thresholds.
- Immutable Pydantic decisions and structured violations with codes, messages, and safe details.
- YAML policy configuration with fail-fast validation and environment-configured path.
- Blocked-query logging with query-run ID, SHA-256 SQL fingerprint, redacted SQL, and violation
  codes. Raw literal values are excluded from the audit record.

## Reuse audit

Phase 2's structured schema snapshot and target SQLAlchemy engine contracts were reused. Phase 2's
structured logger was used by the audit sink, and the existing Pydantic settings/error conventions
were extended. No query result execution was added; that remains Phase 6.

## Guardrail order

1. Empty and length bounds.
2. PostgreSQL AST parsing and exactly-one-statement requirement.
3. SELECT-only, nested query, locking, SELECT INTO, and function policies.
4. Referenced table/column validation against the active schema snapshot.
5. LIMIT injection or clamp.
6. Read-only EXPLAIN cost and estimated-row thresholds.
7. Allow, or record one sanitized blocked-query audit event with all violations.

## Security decisions

- SQL text is never classified with regex alone; policy facts come from an AST.
- Multi-query verification candidates remain separate; executable SQL contains one statement.
- Plan evaluation fails closed when EXPLAIN is unavailable or malformed.
- The plan estimator is invoked only after structural and schema policies pass.
- The EXPLAIN adapter always starts a read-only transaction and rolls it back.
- Literal redaction occurs through AST transformation, with a bounded regex fallback only for
  unparseable audit text.
- Qualified columns resolve against their exact table alias, preventing cross-table name leakage.

## Verification

Executed from `backend/`:

```text
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Result: **55 tests passed**.

New adversarial coverage includes all requested mutation/DDL classes, CTEs, nested selects,
multiple statements, locks, SELECT INTO, dangerous functions, unknown tables/columns, aliases,
LIMIT injection/clamping, expensive plans, missing/failed plans, parse errors, YAML validation,
literal redaction, audit metadata, read-only EXPLAIN, cost extraction, and rollback. All previous
phase tests remain green.

## Environment note

SQLGlot 27.29.0 was installed and used for real AST tests. The PostgreSQL plan adapter was tested
through a deterministic SQLAlchemy-compatible test double because no live PostgreSQL server is
configured locally. Live catalog/EXPLAIN integration remains a production-hardening test gate.

## Next approval gate

Phase 6 will implement the read-only SQL execution engine returning a DataFrame, elapsed time,
rows returned, explain plan, and result metadata with automatic rollback and normalized database
errors. No Phase 6 code has been generated.
