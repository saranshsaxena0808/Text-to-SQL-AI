import unittest

from app.domain.ports.retrieval import EmbeddingProvider
from app.infrastructure.guardrails.parser import SqlGlotPostgresParser
from app.infrastructure.validation.back_translation import RuleBasedBackTranslator
from app.infrastructure.validation.similarity import EmbeddingCosineSimilarity, SqlGlotStructuralSimilarity


class FakeEmbeddings(EmbeddingProvider):
    @property
    def dimension(self):
        return 2

    def embed(self, texts):
        return [[1.0, 0.0], [0.8, 0.6]]


class ValidationAdapterTests(unittest.TestCase):
    def test_embedding_cosine_similarity(self) -> None:
        self.assertAlmostEqual(EmbeddingCosineSimilarity(FakeEmbeddings()).compare("a", "b"), 0.8)

    def test_structural_sql_similarity_ignores_literal_values(self) -> None:
        similarity = SqlGlotStructuralSimilarity().compare(
            "SELECT id FROM users WHERE id = 1", "SELECT id FROM users WHERE id = 99")
        self.assertEqual(similarity, 1.0)

    def test_structural_sql_similarity_detects_different_tables(self) -> None:
        similarity = SqlGlotStructuralSimilarity().compare(
            "SELECT id FROM users", "SELECT amount FROM orders")
        self.assertLess(similarity, 1.0)

    def test_rule_based_back_translation_contains_query_semantics(self) -> None:
        text = RuleBasedBackTranslator(SqlGlotPostgresParser()).translate(
            "SELECT SUM(amount) FROM orders WHERE created_at >= CURRENT_DATE")
        self.assertIn("orders", text)
        self.assertIn("sum", text)
        self.assertIn("created_at", text)
