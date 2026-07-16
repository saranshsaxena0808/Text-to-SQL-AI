from types import TracebackType

from sqlalchemy.orm import Session

from app.domain.ports.unit_of_work import UnitOfWork
from app.infrastructure.persistence.sqlalchemy.connection import ConnectionManager
from app.infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyDataSourceRepository,
    SqlAlchemyFeedbackRepository,
    SqlAlchemyQueryRunRepository,
    SqlAlchemySchemaSnapshotRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._manager = connection_manager
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._manager.new_session()
        self.data_sources = SqlAlchemyDataSourceRepository(self._session)
        self.schema_snapshots = SqlAlchemySchemaSnapshotRepository(self._session)
        self.query_runs = SqlAlchemyQueryRunRepository(self._session)
        self.feedback = SqlAlchemyFeedbackRepository(self._session)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 traceback: TracebackType | None) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of work has not been entered")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
