from uuid import UUID

from app.domain.entities.guardrails import (
    GuardrailDecision, GuardrailPolicy, GuardrailViolation, SqlAnalysis,
)
from app.domain.entities.schema import SchemaSnapshot
from app.domain.exceptions import QueryPlanError, SqlParseError
from app.domain.ports.guardrails import GuardrailAuditSink, QueryPlanEstimator, SqlParser


class GuardrailEngine:
    """Provider-neutral SQL safety policy orchestration."""

    def __init__(self, parser: SqlParser, policy: GuardrailPolicy,
                 audit_sink: GuardrailAuditSink,
                 plan_estimator: QueryPlanEstimator | None = None) -> None:
        self._parser = parser
        self._policy = policy
        self._audit = audit_sink
        self._plans = plan_estimator

    def evaluate(self, sql: str, schema: SchemaSnapshot | None = None,
                 query_run_id: UUID | None = None) -> GuardrailDecision:
        violations: list[GuardrailViolation] = []
        if not sql.strip():
            return self._blocked(sql, [self._violation("SQL_EMPTY", "SQL must not be empty")], query_run_id)
        if len(sql) > self._policy.max_sql_length:
            return self._blocked(sql, [self._violation(
                "SQL_TOO_LONG", "SQL exceeds configured length",
                {"maximum": self._policy.max_sql_length})], query_run_id)
        try:
            analysis = self._parser.analyze(sql)
        except SqlParseError as exc:
            return self._blocked(sql, [self._violation("SQL_PARSE_ERROR", str(exc))], query_run_id)

        violations.extend(self._structural_violations(analysis))
        if schema is not None and not violations:
            violations.extend(self._schema_violations(analysis, schema))
        if violations:
            return self._blocked(sql, violations, query_run_id)

        executable, changed = self._parser.enforce_limit(sql, self._policy.default_limit)
        plan = None
        if self._policy.explain_enabled:
            if self._plans is None:
                return self._blocked(sql, [self._violation(
                    "PLAN_ESTIMATOR_MISSING", "Execution-plan validation is required but unavailable"
                )], query_run_id)
            try:
                plan = self._plans.estimate(executable)
            except QueryPlanError:
                return self._blocked(sql, [self._violation(
                    "PLAN_UNAVAILABLE", "Unable to obtain a safe execution plan"
                )], query_run_id)
            if plan.total_cost > self._policy.max_plan_cost:
                violations.append(self._violation(
                    "PLAN_COST_EXCEEDED", "Estimated query cost exceeds configured maximum",
                    {"estimated_cost": plan.total_cost, "maximum": self._policy.max_plan_cost},
                ))
            if plan.estimated_rows > self._policy.max_estimated_rows:
                violations.append(self._violation(
                    "PLAN_ROWS_EXCEEDED", "Estimated rows exceed configured maximum",
                    {"estimated_rows": plan.estimated_rows,
                     "maximum": self._policy.max_estimated_rows},
                ))
        if violations:
            return self._blocked(sql, violations, query_run_id)
        return GuardrailDecision(allowed=True, original_sql=sql, executable_sql=executable,
                                 injected_limit=changed, plan=plan)

    def _structural_violations(self, analysis: SqlAnalysis) -> list[GuardrailViolation]:
        result = []
        if analysis.statement_count != 1:
            result.append(self._violation("MULTIPLE_STATEMENTS", "Exactly one SQL statement is allowed"))
        if analysis.statement_type.upper() != "SELECT":
            result.append(self._violation("STATEMENT_BLOCKED", "Only SELECT statements are allowed",
                                          {"statement_type": analysis.statement_type.upper()}))
        if analysis.has_nested_query and self._policy.reject_nested_queries:
            result.append(self._violation("NESTED_QUERY_BLOCKED", "Nested queries are not allowed"))
        if analysis.has_locking_clause:
            result.append(self._violation("LOCKING_CLAUSE_BLOCKED", "Row-locking SELECT is not allowed"))
        if analysis.has_select_into:
            result.append(self._violation("SELECT_INTO_BLOCKED", "SELECT INTO is not allowed"))
        blocked = sorted(set(analysis.functions) & set(self._policy.blocked_functions))
        if blocked:
            result.append(self._violation("FUNCTION_BLOCKED", "Query uses blocked functions",
                                          {"functions": blocked}))
        return result

    @staticmethod
    def _schema_violations(analysis: SqlAnalysis, snapshot: SchemaSnapshot) -> list[GuardrailViolation]:
        table_columns: dict[str, set[str]] = {}
        unqualified: dict[str, set[str]] = {}
        for namespace in snapshot.schemas:
            for table in namespace.tables:
                columns = {column.name.lower() for column in table.columns}
                table_columns[f"{namespace.name.lower()}.{table.name.lower()}"] = columns
                unqualified.setdefault(table.name.lower(), set()).update(columns)
        missing_tables = sorted(table for table in analysis.tables
                                if table.lower() not in table_columns
                                and table.split(".")[-1].lower() not in unqualified)
        violations = []
        if missing_tables:
            violations.append(GuardrailEngine._violation(
                "UNKNOWN_TABLE", "Query references tables absent from the schema",
                {"tables": missing_tables}))
        selected_columns: dict[str, set[str]] = {}
        for alias, qualified in analysis.table_aliases.items():
            selected_columns[alias] = table_columns.get(
                qualified, unqualified.get(qualified.split(".")[-1], set())
            )
        available = set().union(*selected_columns.values()) if selected_columns else set()
        missing_columns = set()
        for column in analysis.columns:
            if column.name == "*":
                continue
            if column.table:
                target_columns = selected_columns.get(column.table.lower())
                if target_columns is None or column.name.lower() not in target_columns:
                    missing_columns.add(f"{column.table}.{column.name}")
            elif column.name.lower() not in available:
                missing_columns.add(column.name)
        if missing_columns:
            violations.append(GuardrailEngine._violation(
                "UNKNOWN_COLUMN", "Query references columns absent from selected tables",
                {"columns": sorted(missing_columns)}))
        return violations

    def _blocked(self, sql: str, violations: list[GuardrailViolation],
                 query_run_id: UUID | None) -> GuardrailDecision:
        decision = GuardrailDecision(allowed=False, original_sql=sql, violations=tuple(violations))
        self._audit.record_blocked(decision, self._parser.sanitize(sql), query_run_id)
        return decision

    @staticmethod
    def _violation(code: str, message: str,
                   details: dict[str, object] | None = None) -> GuardrailViolation:
        return GuardrailViolation(code=code, message=message, details=details or {})
