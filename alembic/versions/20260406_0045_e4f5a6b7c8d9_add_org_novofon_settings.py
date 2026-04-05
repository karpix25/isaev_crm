"""add organization novofon settings

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-04-06 00:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_columns = {column["name"] for column in inspector.get_columns("organizations")}

    if "novofon_dial_url_template" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_dial_url_template", sa.String(length=255), nullable=True))
    if "novofon_default_operator_phone" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_default_operator_phone", sa.String(length=32), nullable=True))
    if "novofon_business_card_template" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_template", sa.String(length=5000), nullable=True))
    if "novofon_business_card_site_url" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_site_url", sa.String(length=500), nullable=True))
    if "novofon_business_card_telegram" not in org_columns:
        op.add_column("organizations", sa.Column("novofon_business_card_telegram", sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_columns = {column["name"] for column in inspector.get_columns("organizations")}

    if "novofon_business_card_telegram" in org_columns:
        op.drop_column("organizations", "novofon_business_card_telegram")
    if "novofon_business_card_site_url" in org_columns:
        op.drop_column("organizations", "novofon_business_card_site_url")
    if "novofon_business_card_template" in org_columns:
        op.drop_column("organizations", "novofon_business_card_template")
    if "novofon_default_operator_phone" in org_columns:
        op.drop_column("organizations", "novofon_default_operator_phone")
    if "novofon_dial_url_template" in org_columns:
        op.drop_column("organizations", "novofon_dial_url_template")
