from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities.guardrails import QueryPlanEstimate
from app.domain.exceptions import QueryPlanError
from app.domain.ports.guardrails import QueryPlanEstimator


class PostgresQueryPlanEstimator(QueryPlanEstimator):
    """Runs only PostgreSQL EXPLAIN in an explicitly read-only rolled-back transaction."""

    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("PostgresQueryPlanEstimator requires a PostgreSQL engine")
        self._engine = engine

    def estimate(self, sql: str) -> QueryPlanEstimate:
        try:
            with self._engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    raw = connection.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar_one()
                finally:
                    transaction.rollback()
            document = raw[0] if isinstance(raw, list) else raw
            root = document["Plan"]
            return QueryPlanEstimate(total_cost=float(root["Total Cost"]),
                                     estimated_rows=int(root["Plan Rows"]), plan=document)
        except (SQLAlchemyError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise QueryPlanError("PostgreSQL EXPLAIN failed") from exc
