import math
import re
from itertools import combinations

from app.application.dto.validation import HallucinationContext
from app.application.interfaces.validation import HallucinationCheck
from app.domain.entities.hallucination import ValidationEvidence
from app.domain.ports.validation import BackTranslator, SemanticSimilarity, SqlSimilarity


class BackTranslationCheck(HallucinationCheck):
    name = "back_translation"

    def __init__(self, translator: BackTranslator, similarity: SemanticSimilarity) -> None:
        self._translator, self._similarity = translator, similarity

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        translated = self._translator.translate(context.sql)
        score = self._similarity.compare(context.question, translated)
        return ValidationEvidence(check=self.name, risk=1 - score,
                                  explanation="Question-to-back-translation semantic alignment evaluated.",
                                  details={"similarity": score, "back_translation": translated})


class QuestionSimilarityCheck(HallucinationCheck):
    name = "question_similarity"

    def __init__(self, similarity: SemanticSimilarity) -> None:
        self._similarity = similarity

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        score = self._similarity.compare(context.question, context.explanation)
        return ValidationEvidence(check=self.name, risk=1 - score,
                                  explanation="Question-to-explanation semantic alignment evaluated.",
                                  details={"similarity": score})


class SQLSimilarityCheck(HallucinationCheck):
    name = "sql_similarity"

    def __init__(self, similarity: SqlSimilarity) -> None:
        self._similarity = similarity

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        alternatives = tuple(sql for sql in context.candidate_sql if sql != context.sql)
        if not alternatives:
            return ValidationEvidence(check=self.name, available=False, risk=0,
                                      explanation="No alternative SQL candidate was available.")
        scores = [self._similarity.compare(context.sql, candidate) for candidate in alternatives]
        agreement = sum(scores) / len(scores)
        return ValidationEvidence(check=self.name, risk=1 - agreement,
                                  explanation="Selected SQL was compared structurally with alternatives.",
                                  details={"agreement": agreement, "comparisons": len(scores)})


class ResultValidationCheck(HallucinationCheck):
    name = "result_validation"

    def __init__(self, empty_result_risk: float = 0.25) -> None:
        self._empty_risk = empty_result_risk

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        if not context.execution_succeeded or context.execution is None:
            return ValidationEvidence(check=self.name, risk=1,
                                      explanation="SQL did not execute successfully.")
        frame = context.execution.dataframe
        if frame.empty:
            return ValidationEvidence(check=self.name, risk=self._empty_risk,
                                      explanation="Execution succeeded but returned no rows.")
        invalid = 0
        numeric = 0
        for value in frame.select_dtypes(include="number").to_numpy().ravel():
            numeric += 1
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                invalid += 1
        risk = min(1.0, invalid / numeric) if numeric else 0.0
        return ValidationEvidence(check=self.name, risk=risk,
                                  explanation="Execution result shape and numeric values were validated.",
                                  details={"rows": len(frame), "columns": len(frame.columns),
                                           "invalid_numeric_values": invalid})


class AggregateValidationCheck(HallucinationCheck):
    name = "aggregate_validation"
    _INTENT = re.compile(r"\b(total|sum|average|avg|count|how many|maximum|max|minimum|min)\b", re.I)

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        requested = bool(self._INTENT.search(context.question))
        present = bool(context.analysis.aggregate_functions)
        if requested and not present:
            risk, explanation = 0.9, "Question requests aggregation but SQL has no aggregate."
        elif present and not requested:
            risk, explanation = 0.55, "SQL aggregates although the question has no aggregate intent."
        else:
            risk, explanation = 0.0, "Aggregate intent and SQL structure agree."
        return ValidationEvidence(check=self.name, risk=risk, explanation=explanation,
                                  details={"requested": requested,
                                           "functions": list(context.analysis.aggregate_functions)})


class JoinValidationCheck(HallucinationCheck):
    name = "join_validation"

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        if len(context.analysis.tables) <= 1:
            return ValidationEvidence(check=self.name, risk=0,
                                      explanation="Query uses no multi-table join.")
        edges = self._relationship_edges(context)
        tables = {table.split(".")[-1].lower() for table in context.analysis.tables}
        connected = self._connected(tables, edges)
        join_count_valid = context.analysis.join_count >= len(tables) - 1
        risk = 0.0 if connected and join_count_valid else 0.9
        return ValidationEvidence(check=self.name, risk=risk,
                                  explanation="Joined tables were checked against schema relationships.",
                                  details={"connected": connected, "join_count": context.analysis.join_count})

    @staticmethod
    def _relationship_edges(context: HallucinationContext) -> set[frozenset[str]]:
        edges = set()
        for namespace in context.schema.schemas:
            for table in namespace.tables:
                source = table.name.lower()
                for relation in table.relationships:
                    target = relation.target_table.lower()
                    edges.add(frozenset((source, target)))
        return edges

    @staticmethod
    def _connected(tables: set[str], edges: set[frozenset[str]]) -> bool:
        if not tables:
            return True
        remaining = set(tables)
        reached = {remaining.pop()}
        changed = True
        while changed:
            changed = False
            for table in list(remaining):
                if any(frozenset((table, known)) in edges for known in reached):
                    reached.add(table)
                    remaining.remove(table)
                    changed = True
        return not remaining


class DateValidationCheck(HallucinationCheck):
    name = "date_validation"
    _INTENT = re.compile(r"\b(today|yesterday|week|month|quarter|year|date|daily|monthly|yearly|since|between)\b", re.I)
    _COLUMN = re.compile(r"(date|time|timestamp|created|updated|year|month|day)", re.I)

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        requested = bool(self._INTENT.search(context.question))
        filtered = any(self._COLUMN.search(column) for column in context.analysis.predicate_columns)
        date_function = any(name in {"date_trunc", "extract", "current_date", "current_timestamp"}
                            for name in context.analysis.functions)
        risk = 0.85 if requested and not (filtered or date_function) else 0.0
        return ValidationEvidence(check=self.name, risk=risk,
                                  explanation=("Temporal intent lacks a date predicate." if risk
                                               else "Temporal intent and date filtering are consistent."),
                                  details={"requested": requested, "date_filter": filtered or date_function})


class MultiQueryVerificationCheck(HallucinationCheck):
    name = "multi_query_verification"

    def __init__(self, similarity: SqlSimilarity) -> None:
        self._similarity = similarity

    def evaluate(self, context: HallucinationContext) -> ValidationEvidence:
        candidates = tuple(dict.fromkeys((context.sql,) + context.candidate_sql))
        pairs = list(combinations(candidates, 2))
        if not pairs:
            return ValidationEvidence(check=self.name, available=False, risk=0,
                                      explanation="Multiple SQL candidates were not available.")
        scores = [self._similarity.compare(left, right) for left, right in pairs]
        agreement = sum(scores) / len(scores)
        return ValidationEvidence(check=self.name, risk=1 - agreement,
                                  explanation="Pairwise structural agreement across SQL candidates evaluated.",
                                  details={"agreement": agreement, "pairs": len(pairs)})
