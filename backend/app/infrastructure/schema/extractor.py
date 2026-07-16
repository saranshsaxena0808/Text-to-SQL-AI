import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, MetaData, Table, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.domain.entities.schema import (
    ColumnSchema, ForeignKeySchema, IndexSchema, NamespaceSchema, RelationshipSchema,
    SchemaSnapshot, TableSchema,
)
from app.domain.exceptions import SchemaExtractionError


class SqlAlchemySchemaExtractor:
    """Extracts normalized metadata and bounded samples via SQLAlchemy inspection."""

    def __init__(self, sample_limit: int = 5, excluded_schemas: set[str] | None = None) -> None:
        if not 0 <= sample_limit <= 20:
            raise ValueError("sample_limit must be between 0 and 20")
        self._sample_limit = sample_limit
        self._excluded = excluded_schemas or {"information_schema", "pg_catalog"}

    def extract(self, engine: Engine, data_source_id: UUID,
                schemas: list[str] | None = None) -> SchemaSnapshot:
        inspector = inspect(engine)
        selected = schemas or [s for s in inspector.get_schema_names() if s not in self._excluded]
        try:
            namespaces = tuple(self._extract_namespace(engine, inspector, name)
                               for name in sorted(selected))
            payload = [item.model_dump(mode="json") for item in namespaces]
            checksum = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            return SchemaSnapshot(data_source_id=data_source_id,
                                  captured_at=datetime.now(timezone.utc),
                                  dialect=engine.dialect.name, checksum=checksum,
                                  schemas=namespaces)
        except SQLAlchemyError as exc:
            raise SchemaExtractionError("Unable to extract target schema") from exc

    def _extract_namespace(self, engine: Engine, inspector: Any, schema: str) -> NamespaceSchema:
        tables = tuple(self._extract_table(engine, inspector, schema, name)
                       for name in sorted(inspector.get_table_names(schema=schema)))
        return NamespaceSchema(name=schema, tables=tables)

    def _extract_table(self, engine: Engine, inspector: Any,
                       schema: str, table_name: str) -> TableSchema:
        raw_fks = inspector.get_foreign_keys(table_name, schema=schema)
        foreign_keys = tuple(ForeignKeySchema(
            name=fk.get("name"), constrained_columns=tuple(fk.get("constrained_columns") or ()),
            referred_schema=fk.get("referred_schema"), referred_table=fk["referred_table"],
            referred_columns=tuple(fk.get("referred_columns") or ()),
        ) for fk in raw_fks)
        relationships = tuple(RelationshipSchema(
            from_columns=fk.constrained_columns, target_schema=fk.referred_schema,
            target_table=fk.referred_table, target_columns=fk.referred_columns,
        ) for fk in foreign_keys)
        columns = tuple(ColumnSchema(
            name=column["name"], data_type=str(column["type"]),
            nullable=bool(column.get("nullable", True)),
            default=str(column["default"]) if column.get("default") is not None else None,
            comment=column.get("comment"),
        ) for column in inspector.get_columns(table_name, schema=schema))
        pk = inspector.get_pk_constraint(table_name, schema=schema)
        indexes = tuple(IndexSchema(
            name=index["name"], columns=tuple(index.get("column_names") or ()),
            unique=bool(index.get("unique", False)),
        ) for index in inspector.get_indexes(table_name, schema=schema) if index.get("name"))
        samples = self._sample_values(engine, schema, table_name, columns)
        try:
            comment_info = inspector.get_table_comment(table_name, schema=schema)
        except NotImplementedError:
            comment_info = None
        return TableSchema(name=table_name, columns=columns,
                           primary_key=tuple(pk.get("constrained_columns") or ()),
                           foreign_keys=foreign_keys, relationships=relationships,
                           indexes=indexes, sample_values=samples,
                           comment=comment_info.get("text") if comment_info else None)

    def _sample_values(self, engine: Engine, schema: str, table_name: str,
                       columns: tuple[ColumnSchema, ...]) -> dict[str, tuple[Any, ...]]:
        if self._sample_limit == 0 or not columns:
            return {}
        metadata = MetaData()
        table = Table(table_name, metadata, schema=schema, autoload_with=engine)
        result: dict[str, tuple[Any, ...]] = {}
        with engine.connect() as connection:
            for column in columns:
                statement = (select(table.c[column.name]).where(table.c[column.name].is_not(None))
                             .limit(self._sample_limit))
                result[column.name] = tuple(row[0] for row in connection.execute(statement))
        return result
