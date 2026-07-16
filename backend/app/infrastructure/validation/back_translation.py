from app.domain.ports.guardrails import SqlParser
from app.domain.ports.validation import BackTranslator


class RuleBasedBackTranslator(BackTranslator):
    """Deterministic baseline; an LLM-backed implementation can replace this port later."""

    def __init__(self, parser: SqlParser) -> None:
        self._parser = parser

    def translate(self, sql: str) -> str:
        analysis = self._parser.analyze(sql)
        columns = ", ".join(column.name for column in analysis.columns) or "all columns"
        tables = ", ".join(analysis.tables) or "no table"
        phrases = [f"Retrieve {columns} from {tables}"]
        if analysis.aggregate_functions:
            phrases.append("calculate " + ", ".join(analysis.aggregate_functions))
        if analysis.join_count:
            phrases.append(f"using {analysis.join_count} join")
        if analysis.predicate_columns:
            phrases.append("filtered by " + ", ".join(analysis.predicate_columns))
        if analysis.has_group_by:
            phrases.append("grouped results")
        return "; ".join(phrases)
