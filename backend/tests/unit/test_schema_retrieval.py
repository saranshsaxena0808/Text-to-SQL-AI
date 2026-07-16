import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.application.services.schema_retrieval import SchemaRetrievalService
from app.domain.entities.schema import (
    ColumnSchema, NamespaceSchema, RelationshipSchema, SchemaSnapshot, TableSchema,
)
from app.domain.ports.retrieval import EmbeddingProvider, VectorIndex


class FakeEmbeddings(EmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def dimension(self) -> int:
        return 2

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]


class FakeIndex(VectorIndex):
    def __init__(self, match: str = "sales.orders") -> None:
        self._version = None
        self.keys = []
        self.rebuild_count = 0
        self.match = match

    @property
    def version(self):
        return self._version

    def rebuild(self, keys, vectors, version):
        self.keys = list(keys)
        self._version = version
        self.rebuild_count += 1

    def search(self, vector, limit):
        return [(self.match, 0.95)]


def schema_snapshot() -> SchemaSnapshot:
    users = TableSchema(name="users", columns=(ColumnSchema(
        name="id", data_type="INTEGER", nullable=False),), primary_key=("id",))
    orders = TableSchema(
        name="orders",
        columns=(ColumnSchema(name="id", data_type="INTEGER", nullable=False),
                 ColumnSchema(name="user_id", data_type="INTEGER", nullable=False)),
        primary_key=("id",),
        relationships=(RelationshipSchema(from_columns=("user_id",), target_schema="sales",
                                          target_table="users", target_columns=("id",)),),
    )
    return SchemaSnapshot(data_source_id=uuid4(), captured_at=datetime.now(timezone.utc),
                          dialect="postgresql", checksum="schema-v1",
                          schemas=(NamespaceSchema(name="sales", tables=(orders, users)),))


class SchemaRetrievalServiceTests(unittest.TestCase):
    def test_retrieves_semantic_match_and_relationship_neighbor(self) -> None:
        index = FakeIndex()
        service = SchemaRetrievalService(FakeEmbeddings(), index, top_k=1, max_tables=2)
        result = service.retrieve("orders by user", schema_snapshot())
        self.assertEqual([item.qualified_name for item in result.tables],
                         ["sales.orders", "sales.users"])
        self.assertEqual(result.tables[1].selection_reason, "related_to:sales.orders")
        self.assertEqual(index.rebuild_count, 1)

    def test_reuses_index_when_snapshot_checksum_is_unchanged(self) -> None:
        index = FakeIndex()
        embeddings = FakeEmbeddings()
        service = SchemaRetrievalService(embeddings, index, top_k=1, max_tables=2)
        snapshot = schema_snapshot()
        service.retrieve("first", snapshot)
        service.retrieve("second", snapshot)
        self.assertEqual(index.rebuild_count, 1)
        self.assertEqual(len(embeddings.calls), 3)  # table batch + two questions

    def test_adds_inbound_relationship_neighbor(self) -> None:
        service = SchemaRetrievalService(FakeEmbeddings(), FakeIndex("sales.users"),
                                         top_k=1, max_tables=2)
        result = service.retrieve("users", schema_snapshot())
        self.assertEqual({item.qualified_name for item in result.tables},
                         {"sales.users", "sales.orders"})

    def test_rejects_blank_question(self) -> None:
        with self.assertRaises(ValueError):
            SchemaRetrievalService(FakeEmbeddings(), FakeIndex()).retrieve("  ", schema_snapshot())
