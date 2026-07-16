"""Extend query history and add feedback."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "20260715_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("query_runs", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("query_runs", sa.Column("evaluation", sa.JSON(), nullable=False,
                                          server_default=sa.text("'{}'")))
    op.add_column("query_runs", sa.Column("warnings", sa.JSON(), nullable=False,
                                          server_default=sa.text("'[]'")))
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("query_run_id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False), sa.Column("correction_sql", sa.Text()),
        sa.Column("comment", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["query_run_id"], ["query_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_tenant_id", "feedback", ["tenant_id"])
    op.create_index("ix_feedback_tenant_query", "feedback", ["tenant_id", "query_run_id"])


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_column("query_runs", "warnings")
    op.drop_column("query_runs", "evaluation")
    op.drop_column("query_runs", "confidence")
