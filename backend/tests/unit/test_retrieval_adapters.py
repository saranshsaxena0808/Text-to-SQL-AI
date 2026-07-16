import unittest

from app.infrastructure.retrieval.faiss_index import FaissVectorIndex
from app.infrastructure.retrieval.sentence_transformer import SentenceTransformerEmbeddingProvider


class RetrievalAdapterValidationTests(unittest.TestCase):
    def test_faiss_dimension_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            FaissVectorIndex(0)

    def test_embedding_dimension_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            SentenceTransformerEmbeddingProvider("model", 0)

    def test_empty_embedding_input_does_not_load_model(self) -> None:
        provider = SentenceTransformerEmbeddingProvider("not-installed-or-loaded", 2)
        self.assertEqual(provider.embed([]), [])

    def test_faiss_rebuild_and_cosine_search(self) -> None:
        index = FaissVectorIndex(2)
        index.rebuild(["orders", "users"], [[1.0, 0.0], [0.0, 1.0]], "v1")
        results = index.search([0.99, 0.01], 1)
        self.assertEqual(results[0][0], "orders")
        self.assertGreater(results[0][1], 0.99)
        self.assertEqual(index.version, "v1")
