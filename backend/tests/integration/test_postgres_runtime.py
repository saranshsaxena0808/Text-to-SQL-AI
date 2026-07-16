import os
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, text


URL = os.getenv("TEXT2SQL_TEST_POSTGRES_URL", "")


@unittest.skipUnless(URL, "TEXT2SQL_TEST_POSTGRES_URL is not configured")
class PostgreSqlRuntimeTests(unittest.TestCase):
    """Live PostgreSQL acceptance checks; CI supplies an isolated database."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(URL)
        cls.table = "phase10_" + uuid4().hex
        with cls.engine.begin() as connection:
            connection.execute(text(f"CREATE TABLE {cls.table} (id integer PRIMARY KEY, value text)"))
            connection.execute(text(f"INSERT INTO {cls.table} VALUES (1, 'verified')"))

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {cls.table}"))
        cls.engine.dispose()

    def test_read_only_transaction_reads_and_rejects_writes(self):
        with self.engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET TRANSACTION READ ONLY"))
            value = connection.execute(text(f"SELECT value FROM {self.table}")).scalar_one()
            self.assertEqual(value, "verified")
            with self.assertRaises(Exception):
                connection.execute(text(f"DELETE FROM {self.table}"))
            transaction.rollback()
