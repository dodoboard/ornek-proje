"""jobs and workers

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.String(length=40), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workers")),
    )
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_workers_heartbeat_at"), ["heartbeat_at"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "loading_model",
                "generating_script",
                "generating_storyboard",
                "generating_image",
                "processing_product",
                "generating_video",
                "generating_audio",
                "lip_sync",
                "creating_captions",
                "encoding",
                "completed",
                "failed",
                "cancelled",
                name="job_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=120), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=40), nullable=True),
        sa.Column("project_id", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name=op.f("ck_jobs_progress_range")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_jobs_project_id_projects"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_jobs_project_id"), ["project_id"], unique=False)
        batch_op.create_index("ix_jobs_queue", ["status", "priority", "created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_jobs_type"), ["type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_jobs_type"))
        batch_op.drop_index("ix_jobs_queue")
        batch_op.drop_index(batch_op.f("ix_jobs_project_id"))

    op.drop_table("jobs")
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_workers_heartbeat_at"))

    op.drop_table("workers")
