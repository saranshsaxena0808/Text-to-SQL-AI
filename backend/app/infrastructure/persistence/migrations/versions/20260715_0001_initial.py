"""Create initial control-plane database tables."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("secret_ref", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])
    op.create_index("ix_data_sources_tenant_status", "data_sources", ["tenant_id", "status"])
    op.create_table(
        "schema_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("dialect", sa.String(32), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("structured_schema", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_source_id", "checksum", name="uq_snapshot_source_checksum"),
    )
    op.create_index("ix_schema_snapshots_tenant_id", "schema_snapshots", ["tenant_id"])
    op.create_index("ix_snapshot_source_captured", "schema_snapshots", ["data_source_id", "captured_at"])
    op.create_table(
        "query_runs",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False), sa.Column("generated_sql_redacted", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("model", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)), sa.Column("timings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_query_runs_tenant_id", "query_runs", ["tenant_id"])
    op.create_index("ix_query_runs_tenant_created", "query_runs", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("query_runs")
    op.drop_table("schema_snapshots")
    op.drop_table("data_sources")
