import math

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.domain.ports.retrieval import EmbeddingProvider
from app.domain.ports.validation import SemanticSimilarity, SqlSimilarity


class EmbeddingCosineSimilarity(SemanticSimilarity):
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self._embeddings = embeddings

    def compare(self, left: str, right: str) -> float:
        if not left.strip() or not right.strip():
            return 0.0
        vectors = self._embeddings.embed([left, right])
        if len(vectors) != 2 or len(vectors[0]) != len(vectors[1]):
            return 0.0
        dot = sum(a * b for a, b in zip(vectors[0], vectors[1]))
        left_norm = math.sqrt(sum(value * value for value in vectors[0]))
        right_norm = math.sqrt(sum(value * value for value in vectors[1]))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (left_norm * right_norm)))


class SqlGlotStructuralSimilarity(SqlSimilarity):
    """Jaccard similarity over normalized PostgreSQL AST structural features."""

    def compare(self, left_sql: str, right_sql: str) -> float:
        try:
            left = self._features(sqlglot.parse_one(left_sql, read="postgres"))
            right = self._features(sqlglot.parse_one(right_sql, read="postgres"))
        except ParseError:
            return 0.0
        if not left and not right:
            return 1.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _features(statement: exp.Expression) -> set[str]:
        features: set[str] = set()
        for node in statement.walk():
            features.add(f"node:{type(node).__name__.lower()}")
            if isinstance(node, exp.Table):
                features.add(f"table:{node.db.lower()}.{node.name.lower()}" if node.db
                             else f"table:{node.name.lower()}")
            elif isinstance(node, exp.Column):
                features.add(f"column:{node.name.lower()}")
            elif isinstance(node, exp.Func):
                name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
                features.add(f"function:{name.lower()}")
            elif isinstance(node, exp.Literal):
                features.add("literal:string" if node.is_string else "literal:number")
        return features
