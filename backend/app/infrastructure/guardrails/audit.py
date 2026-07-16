import hashlib
from uuid import UUID

from app.domain.entities.guardrails import GuardrailDecision
from app.domain.ports.guardrails import GuardrailAuditSink
from app.infrastructure.observability import get_logger


logger = get_logger(__name__)


class LoggingGuardrailAuditSink(GuardrailAuditSink):
    def record_blocked(self, decision: GuardrailDecision, sanitized_sql: str,
                       query_run_id: UUID | None = None) -> None:
        logger.warning("SQL query blocked by guardrails", extra={
            "event": "guardrail_blocked",
            "query_run_id": str(query_run_id) if query_run_id else None,
            "sql_sha256": hashlib.sha256(decision.original_sql.encode("utf-8")).hexdigest(),
            "sanitized_sql": sanitized_sql,
            "violation_codes": [violation.code for violation in decision.violations],
        })
