"""scripts and storyboards

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scripts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("llm_model", sa.String(length=80), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("hook", sa.String(length=200), nullable=False),
        sa.Column("cta", sa.String(length=200), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.JSON(), nullable=False),
        sa.Column("fact_report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_scripts_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scripts")),
    )
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scripts_project_id"), ["project_id"], unique=False)

    op.create_table(
        "storyboards",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("script_id", sa.String(length=40), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_storyboards_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["script_id"], ["scripts.id"], name=op.f("fk_storyboards_script_id_scripts"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storyboards")),
    )
    with op.batch_alter_table("storyboards", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_storyboards_project_id"), ["project_id"], unique=False)

    op.create_table(
        "shots",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("storyboard_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dialogue", sa.Text(), nullable=False),
        sa.Column("on_screen_text", sa.String(length=200), nullable=False),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("camera", sa.String(length=40), nullable=False),
        sa.Column("camera_motion", sa.String(length=40), nullable=False),
        sa.Column("generation_method", sa.String(length=40), nullable=False),
        sa.Column("disclosure_label", sa.String(length=40), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("keyframe_asset_id", sa.String(length=40), nullable=True),
        sa.Column("clip_asset_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["clip_asset_id"], ["assets.id"], name=op.f("fk_shots_clip_asset_id_assets"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["keyframe_asset_id"],
            ["assets.id"],
            name=op.f("fk_shots_keyframe_asset_id_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["storyboard_id"],
            ["storyboards.id"],
            name=op.f("fk_shots_storyboard_id_storyboards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shots")),
    )
    with op.batch_alter_table("shots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_shots_storyboard_id"), ["storyboard_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("shots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_shots_storyboard_id"))

    op.drop_table("shots")
    with op.batch_alter_table("storyboards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_storyboards_project_id"))

    op.drop_table("storyboards")
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scripts_project_id"))

    op.drop_table("scripts")
