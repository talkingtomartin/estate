"""Add purchase_price and current_value to properties

Revision ID: 004
Revises: 003
Create Date: 2026-03-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("purchase_price", sa.Float(), nullable=True))
    op.add_column("properties", sa.Column("current_value", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "current_value")
    op.drop_column("properties", "purchase_price")
