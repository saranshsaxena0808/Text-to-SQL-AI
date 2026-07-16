import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine

from app.config.settings import DatabaseSettings
from app.domain.entities.data_source import DataSource
from app.domain.entities.schema import NamespaceSchema, SchemaSnapshot
from app.domain.entities.query import Feedback, QueryRun, QueryStatus
from app.infrastructure.persistence.sqlalchemy.connection import ConnectionManager
from app.infrastructure.persistence.sqlalchemy.models import Base
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.manager = ConnectionManager(DatabaseSettings(), engine=self.engine)
        self.tenant_id = uuid4()
        now = datetime.now(timezone.utc)
        self.source = DataSource(tenant_id=self.tenant_id, name="warehouse",
                                 secret_ref="vault://warehouse", created_at=now, updated_at=now)

    def tearDown(self) -> None:
        self.manager.dispose()

    def test_data_source_is_tenant_scoped(self) -> None:
        with SqlAlchemyUnitOfWork(self.manager) as uow:
            uow.data_sources.add(self.source)
            uow.commit()

        with SqlAlchemyUnitOfWork(self.manager) as uow:
            loaded = uow.data_sources.get(self.source.id, self.tenant_id)
            leaked = uow.data_sources.get(self.source.id, uuid4())
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, self.source.id)
        self.assertEqual(loaded.tenant_id, self.source.tenant_id)
        self.assertEqual(loaded.secret_ref, self.source.secret_ref)
        self.assertIsNone(leaked)

    def test_schema_snapshot_round_trip(self) -> None:
        snapshot = SchemaSnapshot(data_source_id=self.source.id, captured_at=datetime.now(timezone.utc),
                                  dialect="postgresql", checksum="a" * 64,
                                  schemas=(NamespaceSchema(name="public", tables=()),))
        with SqlAlchemyUnitOfWork(self.manager) as uow:
            uow.data_sources.add(self.source)
            uow.schema_snapshots.add(snapshot, self.tenant_id)
            uow.commit()
        with SqlAlchemyUnitOfWork(self.manager) as uow:
            loaded = uow.schema_snapshots.latest(self.source.id, self.tenant_id)
        self.assertEqual(loaded, snapshot)

    def test_query_history_is_tenant_scoped_and_feedback_persists(self) -> None:
        with SqlAlchemyUnitOfWork(self.manager) as uow:
            uow.data_sources.add(self.source)
            run = QueryRun(tenant_id=self.tenant_id, user_id=uuid4(),
                           data_source_id=self.source.id, question="question",
                           generated_sql_redacted="SELECT '[REDACTED]'", status=QueryStatus.COMPLETED,
                           confidence=0.8, evaluation={"safe": True}, timings={"total_ms": 1.2},
                           warnings=("warning",), created_at=datetime.now(timezone.utc))
            uow.query_runs.add(run)
            feedback = Feedback(tenant_id=self.tenant_id, user_id=run.user_id,
                                query_run_id=run.id, rating=5,
                                created_at=datetime.now(timezone.utc))
            uow.feedback.add(feedback)
            uow.commit()
        with SqlAlchemyUnitOfWork(self.manager) as uow:
            loaded = uow.query_runs.get(run.id, self.tenant_id)
            leaked = uow.query_runs.get(run.id, uuid4())
            listed = uow.query_runs.list_for_tenant(self.tenant_id, 10)
        self.assertEqual(loaded.id, run.id)
        self.assertEqual(loaded.warnings, ("warning",))
        self.assertIsNone(leaked)
        self.assertEqual([item.id for item in listed], [run.id])
