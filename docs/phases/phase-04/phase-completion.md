# Phase 4 Completion — Groq Integration

Status: **Complete**

## Delivered

- Provider-neutral `LLMGateway` port and immutable generation/stream contracts.
- Pydantic `SqlGenerationResult` containing SQL, confidence, explanation, referenced tables,
  referenced columns, clarification flag, and clarification question.
- Groq SDK adapter with configurable model allowlist, strict-model set, timeout, token cap,
  temperature, seed, retry count, and exponential backoff.
- Non-streaming JSON Schema Structured Outputs with mandatory Pydantic validation.
- Streaming JSON Object mode with delta events and mandatory final Pydantic validation.
- `retry-after` support for HTTP 429 and exponential backoff with bounded jitter for transient
  connection, timeout, and server errors.
- Explicit model rejection before any provider request.
- Normalized provider-neutral errors for configuration, rate limits, unavailable service,
  malformed responses, and model refusals.
- Structured retry logs containing model, attempt, delay, and status only; prompts and keys are
  excluded.
- Token usage, request ID, selected model, and system fingerprint response metadata.
- Secret API-key configuration and Groq SDK dependency declaration.

## Reuse audit

Phase 3's `BuiltPrompt` contract and dynamic prompt output schema were reused. The existing
Pydantic settings, exception structure, and structured logging infrastructure were extended.
No prompt construction, schema retrieval, SQL validation, or business scoring logic was placed
inside the Groq adapter.

## Design decisions

- The adapter disables SDK retries and owns retry policy centrally for deterministic telemetry.
- Strict Structured Outputs are enabled only for configured supported models.
- Groq currently does not support Structured Outputs together with streaming, so the streaming
  path requests JSON Object mode, emits raw deltas, and emits `completed` only after the assembled
  object passes Pydantic validation.
- A failure after streaming has emitted deltas is not replayed automatically; replaying would
  duplicate client-visible output. Only stream establishment is retryable.
- Provider confidence is captured but remains untrusted input; the platform confidence engine
  will calculate the final score in a later phase.

## Verification

Commands executed from `backend/`:

```text
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Result: **35 tests passed**.

New tests cover strict and best-effort model payloads, allowlist enforcement, schema decoding,
usage metadata, refusal handling, invalid response normalization, `retry-after`, retry exhaustion,
non-retryable errors, missing keys, invalid configuration, streaming deltas, and typed stream
completion. All earlier phase regression tests remain green. No live Groq request was made.

## Documentation basis

- Groq Structured Outputs documentation: strict JSON Schema behavior, supported-model limits,
  and the current streaming incompatibility.
- Groq rate-limit documentation: HTTP 429 and `retry-after` semantics.
- Groq Chat Completions API reference: `max_completion_tokens`, seed, response metadata, and
  request/response shapes.
- Installed official Groq Python SDK 0.37.1 signature was inspected locally.

## Next approval gate

Phase 5 will implement AST-based SQL validation and configurable guardrails, including blocked
statements, nested-query rejection, LIMIT injection, plan-cost policy, structured errors, and
blocked-query audit logging. No Phase 5 code has been generated.
