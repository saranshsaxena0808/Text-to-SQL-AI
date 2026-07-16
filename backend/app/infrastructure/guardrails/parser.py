import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.domain.entities.guardrails import ColumnReference, SqlAnalysis
from app.domain.exceptions import SqlParseError
from app.domain.ports.guardrails import SqlParser


class SqlGlotPostgresParser(SqlParser):
    def analyze(self, sql: str) -> SqlAnalysis:
        try:
            parsed = [statement for statement in sqlglot.parse(sql, read="postgres")
                      if statement is not None]
        except ParseError as exc:
            raise SqlParseError("SQL syntax is invalid") from exc
        if not parsed:
            raise SqlParseError("SQL contains no statement")
        root = parsed[0]
        tables = tuple(sorted({self._qualified_table(table) for statement in parsed
                               for table in statement.find_all(exp.Table)}))
        aliases = {table.alias_or_name.lower(): self._qualified_table(table).lower()
                   for statement in parsed for table in statement.find_all(exp.Table)}
        columns = tuple(ColumnReference(table=column.table or None, name=column.name)
                        for statement in parsed for column in statement.find_all(exp.Column))
        functions = tuple(sorted({self._function_name(function) for statement in parsed
                                  for function in statement.find_all(exp.Func)}))
        aggregate_functions = tuple(sorted({self._function_name(function) for statement in parsed
                                             for function in statement.find_all(exp.AggFunc)}))
        predicate_columns = tuple(sorted({column.name for statement in parsed
                                          for where in statement.find_all(exp.Where)
                                          for column in where.find_all(exp.Column)}))
        select_count = sum(1 for statement in parsed for _ in statement.find_all(exp.Select))
        limit = self._integer_limit(root)
        return SqlAnalysis(
            statement_count=len(parsed), statement_type=self._statement_type(root),
            tables=tables, table_aliases=aliases, columns=columns, functions=functions,
            has_nested_query=select_count > 1 or any(
                isinstance(node, exp.Subquery) for statement in parsed for node in statement.walk()
            ),
            has_locking_clause=any(bool(statement.args.get("locks")) for statement in parsed),
            has_select_into=any(bool(select.args.get("into")) for statement in parsed
                                for select in statement.find_all(exp.Select)),
            join_count=sum(1 for statement in parsed for _ in statement.find_all(exp.Join)),
            aggregate_functions=aggregate_functions,
            has_group_by=any(bool(select.args.get("group")) for statement in parsed
                             for select in statement.find_all(exp.Select)),
            predicate_columns=predicate_columns,
            limit=limit,
        )

    def enforce_limit(self, sql: str, maximum: int) -> tuple[str, bool]:
        try:
            statement = sqlglot.parse_one(sql, read="postgres")
        except ParseError as exc:
            raise SqlParseError("SQL syntax is invalid") from exc
        current = self._integer_limit(statement)
        if current is not None and current <= maximum:
            return statement.sql(dialect="postgres"), False
        rewritten = statement.copy().limit(maximum)
        return rewritten.sql(dialect="postgres"), True

    def sanitize(self, sql: str) -> str:
        try:
            statements = sqlglot.parse(sql, read="postgres")
            sanitized = []
            for statement in statements:
                if statement is None:
                    continue
                redacted = statement.transform(
                    lambda node: exp.Literal.string("[REDACTED]") if isinstance(node, exp.Literal) else node,
                    copy=True,
                )
                sanitized.append(redacted.sql(dialect="postgres"))
            return "; ".join(sanitized) or "[UNPARSEABLE SQL]"
        except ParseError:
            without_strings = re.sub(r"'(?:''|[^'])*'", "'[REDACTED]'", sql)
            return re.sub(r"\b\d+(?:\.\d+)?\b", "[NUMBER]", without_strings)[:10000]

    @staticmethod
    def _statement_type(statement: exp.Expression) -> str:
        return "SELECT" if isinstance(statement, exp.Select) else type(statement).__name__.upper()

    @staticmethod
    def _qualified_table(table: exp.Table) -> str:
        parts = [part for part in (table.catalog, table.db, table.name) if part]
        return ".".join(parts)

    @staticmethod
    def _integer_limit(statement: exp.Expression) -> int | None:
        limit = statement.args.get("limit")
        expression = getattr(limit, "expression", None)
        if isinstance(expression, exp.Literal) and not expression.is_string:
            try:
                return int(expression.this)
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _function_name(function: exp.Func) -> str:
        if isinstance(function, exp.Anonymous):
            return function.name.lower()
        return function.sql_name().lower()
