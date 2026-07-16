from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import DatabaseSettings
from app.domain.exceptions import DatabaseConnectionError


class ConnectionManager:
    """Owns the control-plane engine and session factory."""

    def __init__(self, settings: DatabaseSettings, engine: Engine | None = None) -> None:
        self._engine = engine or create_engine(
            settings.url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout_seconds,
            pool_recycle=settings.pool_recycle_seconds,
        )
        self._sessions = sessionmaker(
            bind=self._engine, class_=Session, expire_on_commit=False, autoflush=False
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def new_session(self) -> Session:
        return self._sessions()

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.new_session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def healthcheck(self) -> bool:
        from sqlalchemy import text

        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            raise DatabaseConnectionError("Control database healthcheck failed") from exc

    def dispose(self) -> None:
        self._engine.dispose()
