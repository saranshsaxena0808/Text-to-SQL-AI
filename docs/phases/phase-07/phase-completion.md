# Phase 7 Completion — Hallucination and Confidence Engines

Status: **Complete**

## Delivered

- Independent hallucination-check Strategy interface and typed application context.
- Back-translation validation through replaceable `BackTranslator` and semantic-similarity ports.
- Deterministic rule-based SQL back translator as the offline baseline implementation.
- Question-to-explanation semantic similarity using the existing embedding abstraction.
- AST structural SQL similarity that ignores literal values while retaining tables, columns,
  functions, and operator structure.
- Result validation for execution failure, empty results, invalid numeric values, and result shape.
- Aggregate-intent validation against parsed aggregate functions and grouping facts.
- Join validation against schema relationships with mixed qualified/unqualified identifier support.
- Date-intent validation against date predicate columns and temporal functions.
- Selected-candidate SQL similarity and pairwise multi-query verification.
- Weighted hallucination probability with evidence availability, weight renormalization, policy
  version, per-check explanations/details, and top-risk summary.
- Check isolation: an internal validator failure is captured as unavailable evidence without
  leaking internal details or aborting all remaining checks.
- Confidence engine combining syntax score, schema coverage, execution success, inverse
  hallucination risk, multi-query agreement, and explainability.
- Normalized confidence breakdown with raw scores, weights, contributions, policy version, final
  score, and actionable warnings.
- Versioned YAML policies and environment-configured policy paths.
- Extended PostgreSQL AST analysis for joins, aggregates, grouping, and predicate columns.

## Reuse audit

Existing schema snapshots, SQL parser, embedding provider, Groq explanation contract, execution
DataFrame result, and explain-plan/result DTOs were reused. No duplicate embedding model, SQL
parser, result execution path, or provider confidence calculation was introduced.

## Validation pipeline

1. Translate SQL back to a semantic description and compare it with the question.
2. Compare the question with the generated explanation independently.
3. Compare selected SQL structurally with alternate candidates.
4. Validate execution/result characteristics.
5. Validate aggregate, join, and temporal intent against AST/schema facts.
6. Measure pairwise agreement across independently generated SQL candidates.
7. Aggregate available evidence with versioned weights into hallucination probability.
8. Combine independent quality signals into final confidence and warnings.

## Design and safety decisions

- Provider-reported confidence remains untrusted and is not used as final platform confidence.
- Validators return evidence rather than booleans, preserving explainability and calibration data.
- Missing multi-query evidence is marked unavailable instead of being treated as agreement.
- Available weights are renormalized; if no evidence exists, hallucination probability fails
  closed to `1.0`.
- SQL similarity uses AST features, not formatting-sensitive string comparison.
- Join validation uses extracted foreign-key relationships and a connectivity check.
- Result validators inspect bounded Phase 6 DataFrames and never trigger execution themselves.
- No raw row values are added to validation evidence.

## Verification

Executed from `backend/`:

```text
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Result: **83 tests passed**.

New coverage includes back translation, semantic similarity, structural SQL similarity, literal
normalization, candidate absence, pairwise verification, execution failure, empty/invalid results,
aggregate mismatch, relationship/disconnected joins, mixed qualification, date mismatch, weighted
probability, unavailable evidence, contained validator failures, confidence math, breakdowns,
warnings, invalid weights, and shipped YAML policies. All earlier phase tests remain green.

## Calibration note

The architecture and implementation are production-shaped, but the default weights, thresholds,
keyword intent rules, and rule-based back translation are initial baselines. They must be calibrated
against a tenant-representative labeled Text-to-SQL evaluation set before production accuracy or
probability calibration claims are made. Phase 10 retains this as a release gate. The back-
translation port intentionally allows a stronger LLM-backed implementation without changing the
engine.

## Next approval gate

Phase 8 will implement application orchestration and FastAPI: query/schema/history/feedback/health
endpoints, composition-root dependency wiring, request/error contracts, middleware, and API tests.
No Phase 8 code has been generated.
