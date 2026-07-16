from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ColumnSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    comment: str | None = None


class ForeignKeySchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str | None = None
    constrained_columns: tuple[str, ...]
    referred_schema: str | None = None
    referred_table: str
    referred_columns: tuple[str, ...]


class RelationshipSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    from_columns: tuple[str, ...]
    target_schema: str | None = None
    target_table: str
    target_columns: tuple[str, ...]


class IndexSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    columns: tuple[str, ...]
    unique: bool = False


class TableSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    columns: tuple[ColumnSchema, ...]
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKeySchema, ...] = ()
    relationships: tuple[RelationshipSchema, ...] = ()
    indexes: tuple[IndexSchema, ...] = ()
    sample_values: dict[str, tuple[Any, ...]] = Field(default_factory=dict)
    comment: str | None = None


class NamespaceSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    tables: tuple[TableSchema, ...]


class SchemaSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    data_source_id: UUID
    captured_at: datetime
    dialect: str
    checksum: str
    schemas: tuple[NamespaceSchema, ...]
