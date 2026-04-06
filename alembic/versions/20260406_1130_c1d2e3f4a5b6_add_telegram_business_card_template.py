"""add telegram business card template to organizations

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-04-06 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_columns = {column["name"] for column in inspector.get_columns("organizations")}
    if "telegram_business_card_template" not in org_columns:
        op.add_column("organizations", sa.Column("telegram_business_card_template", sa.String(length=5000), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_columns = {column["name"] for column in inspector.get_columns("organizations")}
    if "telegram_business_card_template" in org_columns:
        op.drop_column("organizations", "telegram_business_card_template")
