"""change users.telegram_user_id to BIGINT

Revision ID: 20250920_01
Revises: 
Create Date: 2025-09-20
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20250920_01"
down_revision = "20250919_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users 
        ALTER COLUMN telegram_user_id 
        TYPE BIGINT 
        USING telegram_user_id::BIGINT;
        """
    )


def downgrade() -> None:
    # אופציונלי: החזרה ל-Integer
    op.execute(
        """
        ALTER TABLE users 
        ALTER COLUMN telegram_user_id 
        TYPE INTEGER 
        USING telegram_user_id::INTEGER;
        """
    )

