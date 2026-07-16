import unittest

from sqlalchemy import create_engine, text

from app.config.settings import DatabaseSettings
from app.infrastructure.persistence.sqlalchemy.connection import ConnectionManager


class ConnectionManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.manager = ConnectionManager(DatabaseSettings(), engine=self.engine)

    def tearDown(self) -> None:
        self.manager.dispose()

    def test_healthcheck(self) -> None:
        self.assertTrue(self.manager.healthcheck())

    def test_context_rolls_back_on_error(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE item (id INTEGER PRIMARY KEY)"))

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with self.manager.session() as session:
                session.execute(text("INSERT INTO item (id) VALUES (1)"))
                raise RuntimeError("boom")

        with self.engine.connect() as connection:
            count = connection.scalar(text("SELECT COUNT(*) FROM item"))
        self.assertEqual(count, 0)
