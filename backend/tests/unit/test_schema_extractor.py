import unittest
from uuid import uuid4

from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, String, Table, create_engine

from app.infrastructure.schema.extractor import SqlAlchemySchemaExtractor


class SchemaExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        metadata = MetaData()
        users = Table("users", metadata, Column("id", Integer, primary_key=True),
                      Column("email", String, nullable=False, unique=True))
        orders = Table("orders", metadata, Column("id", Integer, primary_key=True),
                       Column("user_id", ForeignKey("users.id"), nullable=False),
                       Column("total", Integer, nullable=False))
        Index("ix_orders_total", orders.c.total)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(users.insert(), [{"id": 1, "email": "a@example.com"}])
            connection.execute(orders.insert(), [{"id": 10, "user_id": 1, "total": 42}])

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_extracts_structured_schema_and_samples(self) -> None:
        snapshot = SqlAlchemySchemaExtractor(sample_limit=2).extract(
            self.engine, uuid4(), schemas=["main"]
        )
        tables = {table.name: table for table in snapshot.schemas[0].tables}
        self.assertEqual(tables["orders"].primary_key, ("id",))
        self.assertEqual(tables["orders"].foreign_keys[0].referred_table, "users")
        self.assertEqual(tables["orders"].relationships[0].target_columns, ("id",))
        self.assertEqual(tables["orders"].indexes[0].name, "ix_orders_total")
        self.assertEqual(tables["orders"].sample_values["total"], (42,))
        self.assertEqual(len(snapshot.checksum), 64)
        serialized = snapshot.model_dump(mode="json")
        self.assertEqual(serialized["schemas"][0]["name"], "main")

    def test_zero_sample_limit_skips_sampling(self) -> None:
        snapshot = SqlAlchemySchemaExtractor(sample_limit=0).extract(
            self.engine, uuid4(), schemas=["main"]
        )
        self.assertTrue(all(not table.sample_values for table in snapshot.schemas[0].tables))

    def test_sampling_does_not_require_database_equality_operator(self) -> None:
        """Samples are bounded rows, not DISTINCT values (unsupported by PostgreSQL JSON)."""
        orders = Table("orders", MetaData(), autoload_with=self.engine)
        with self.engine.begin() as connection:
            connection.execute(orders.insert(), {"id": 11, "user_id": 1, "total": 42})
        snapshot = SqlAlchemySchemaExtractor(sample_limit=2).extract(
            self.engine, uuid4(), schemas=["main"]
        )
        table = next(item for item in snapshot.schemas[0].tables if item.name == "orders")
        self.assertEqual(table.sample_values["total"], (42, 42))
