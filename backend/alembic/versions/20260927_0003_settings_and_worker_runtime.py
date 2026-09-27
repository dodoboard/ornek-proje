"""settings and worker runtime

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("runtime", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workers", schema=None) as batch_op:
        batch_op.drop_column("runtime")

    op.drop_table("settings")
