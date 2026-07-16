from collections import OrderedDict
from threading import RLock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url


class TargetEngineRegistry:
    """Thread-safe bounded registry for target database engines."""

    def __init__(self, max_size: int = 32, statement_timeout_ms: int = 30_000) -> None:
        if max_size < 1:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._statement_timeout_ms = statement_timeout_ms
        self._engines: OrderedDict[str, Engine] = OrderedDict()
        self._lock = RLock()

    def get_or_create(self, key: str, database_url: str) -> Engine:
        with self._lock:
            if key in self._engines:
                self._engines.move_to_end(key)
                return self._engines[key]
            dialect_name = make_url(database_url).get_backend_name()
            pool_options = {} if dialect_name == "sqlite" else {"pool_size": 5, "max_overflow": 5}
            engine = create_engine(database_url, pool_pre_ping=True, **pool_options)
            if engine.dialect.name == "postgresql":
                timeout = self._statement_timeout_ms

                @event.listens_for(engine, "connect")
                def configure_connection(dbapi_connection: object, _: object) -> None:
                    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
                    try:
                        cursor.execute(f"SET statement_timeout = {timeout:d}")
                    finally:
                        cursor.close()
            self._engines[key] = engine
            if len(self._engines) > self._max_size:
                _, evicted = self._engines.popitem(last=False)
                evicted.dispose()
            return engine

    def remove(self, key: str) -> None:
        with self._lock:
            engine = self._engines.pop(key, None)
            if engine:
                engine.dispose()

    def dispose_all(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
