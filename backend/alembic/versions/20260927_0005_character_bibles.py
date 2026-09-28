"""character bibles

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_bibles",
        sa.Column("character_id", sa.String(length=40), nullable=False),
        sa.Column("visual_descriptors", sa.JSON(), nullable=False),
        sa.Column("immutable_traits", sa.JSON(), nullable=False),
        sa.Column("mutable_traits", sa.JSON(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("negative_prompts", sa.JSON(), nullable=False),
        sa.Column("generation_settings", sa.JSON(), nullable=False),
        sa.Column("seed_history", sa.JSON(), nullable=False),
        sa.Column("lora", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_character_bibles_character_id_characters"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("character_id", name=op.f("pk_character_bibles")),
    )


def downgrade() -> None:
    op.drop_table("character_bibles")
