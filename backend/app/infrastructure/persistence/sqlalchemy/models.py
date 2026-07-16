import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DataSourceModel(Base):
    __tablename__ = "data_sources"
    __table_args__ = (Index("ix_data_sources_tenant_status", "tenant_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshots: Mapped[list["SchemaSnapshotModel"]] = relationship(back_populates="data_source")


class SchemaSnapshotModel(Base):
    __tablename__ = "schema_snapshots"
    __table_args__ = (
        UniqueConstraint("data_source_id", "checksum", name="uq_snapshot_source_checksum"),
        Index("ix_snapshot_source_captured", "data_source_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    dialect: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    structured_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    data_source: Mapped[DataSourceModel] = relationship(back_populates="snapshots")


class QueryRunModel(Base):
    __tablename__ = "query_runs"
    __table_args__ = (Index("ix_query_runs_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    data_source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql_redacted: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    timings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float | None]
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedbackModel(Base):
    __tablename__ = "feedback"
    __table_args__ = (Index("ix_feedback_tenant_query", "tenant_id", "query_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    query_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False)
    correction_sql: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
