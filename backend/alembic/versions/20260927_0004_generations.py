"""generations

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.String(length=40), nullable=True),
        sa.Column("project_id", sa.String(length=40), nullable=True),
        sa.Column("character_id", sa.String(length=40), nullable=True),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model_key", sa.String(length=80), nullable=False),
        sa.Column("model_source", sa.String(length=500), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("seeds", sa.JSON(), nullable=False),
        sa.Column("input_asset_ids", sa.JSON(), nullable=False),
        sa.Column("output_asset_ids", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("device", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_generations_character_id_characters"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_generations_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_generations_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generations")),
    )
    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_generations_character_id"), ["character_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_generations_kind"), ["kind"], unique=False)
        batch_op.create_index(batch_op.f("ix_generations_project_id"), ["project_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("generations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_generations_project_id"))
        batch_op.drop_index(batch_op.f("ix_generations_kind"))
        batch_op.drop_index(batch_op.f("ix_generations_character_id"))

    op.drop_table("generations")
