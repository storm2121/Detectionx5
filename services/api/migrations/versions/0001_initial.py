"""Initial schema: reads, read views, the review queue, jobs and exports.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "reads",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("plate", sa.String(32), nullable=True),
        sa.Column("text", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("calibrated", sa.Boolean(), nullable=False),
        sa.Column("prediction_set", sa.JSON(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=True),
        sa.Column("fusion", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("posterior", sa.JSON(), nullable=False),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
    )
    op.create_index("ix_reads_created_at", "reads", ["created_at"])
    op.create_index("ix_reads_status", "reads", ["status"])
    op.create_index("ix_reads_job_id", "reads", ["job_id"])

    op.create_table(
        "read_views",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "read_id", sa.String(32), sa.ForeignKey("reads.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("crop_path", sa.Text(), nullable=True),
        sa.Column("box", sa.JSON(), nullable=False),
        sa.Column("detector_confidence", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("prediction", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("hypotheses", sa.JSON(), nullable=False),
        sa.Column("prediction_set", sa.JSON(), nullable=False),
    )
    op.create_index("ix_read_views_read_id", "read_views", ["read_id"])

    op.create_table(
        "review_items",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "read_id",
            sa.String(32),
            sa.ForeignKey("reads.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("corrected_plate", sa.String(32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_items_created_at", "review_items", ["created_at"])
    op.create_index("ix_review_items_status", "review_items", ["status"])

    op.create_table(
        "exports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_index("ix_review_items_status", "review_items")
    op.drop_index("ix_review_items_created_at", "review_items")
    op.drop_table("review_items")
    op.drop_index("ix_read_views_read_id", "read_views")
    op.drop_table("read_views")
    op.drop_index("ix_reads_job_id", "reads")
    op.drop_index("ix_reads_status", "reads")
    op.drop_index("ix_reads_created_at", "reads")
    op.drop_table("reads")
    op.drop_index("ix_jobs_status", "jobs")
    op.drop_index("ix_jobs_created_at", "jobs")
    op.drop_table("jobs")
