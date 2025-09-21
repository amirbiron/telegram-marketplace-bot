"""change users.id and related FKs to BIGINT

Revision ID: 20250921_01
Revises: 20250920_01
Create Date: 2025-09-21
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20250921_01"
down_revision = "20250920_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) לשדרג את ה-PK של users ל-BIGINT
    op.execute(
        """
        ALTER TABLE users 
        ALTER COLUMN id 
        TYPE BIGINT 
        USING id::BIGINT;
        """
    )

    # 2) לעדכן את ה-sequence ל-BIGINT
    op.execute("ALTER SEQUENCE users_id_seq AS BIGINT;")

    # 3) לעדכן את כל ה-FK Columns ל-BIGINT
    statements = [
        # user.py models
        "ALTER TABLE seller_profiles ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT;",
        "ALTER TABLE seller_profiles ALTER COLUMN verified_by_admin_id TYPE BIGINT USING verified_by_admin_id::BIGINT;",
        "ALTER TABLE wallets ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT;",
        "ALTER TABLE transactions ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT;",
        "ALTER TABLE transactions ALTER COLUMN processed_by_admin_id TYPE BIGINT USING processed_by_admin_id::BIGINT;",
        "ALTER TABLE fund_locks ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT;",

        # order.py models
        "ALTER TABLE orders ALTER COLUMN buyer_id TYPE BIGINT USING buyer_id::BIGINT;",
        "ALTER TABLE orders ALTER COLUMN seller_id TYPE BIGINT USING seller_id::BIGINT;",
        "ALTER TABLE orders ALTER COLUMN resolved_by_admin_id TYPE BIGINT USING resolved_by_admin_id::BIGINT;",
        "ALTER TABLE auctions ALTER COLUMN seller_id TYPE BIGINT USING seller_id::BIGINT;",
        "ALTER TABLE auctions ALTER COLUMN winner_id TYPE BIGINT USING winner_id::BIGINT;",
        "ALTER TABLE auction_bids ALTER COLUMN bidder_id TYPE BIGINT USING bidder_id::BIGINT;",

        # coupon.py models
        "ALTER TABLE coupons ALTER COLUMN seller_id TYPE BIGINT USING seller_id::BIGINT;",
        "ALTER TABLE user_favorites ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT;",
        "ALTER TABLE coupon_ratings ALTER COLUMN buyer_id TYPE BIGINT USING buyer_id::BIGINT;",
        "ALTER TABLE coupon_ratings ALTER COLUMN seller_id TYPE BIGINT USING seller_id::BIGINT;",
    ]

    for stmt in statements:
        op.execute(stmt)


def downgrade() -> None:
    # החזרה של ה-FK Columns ל-INTEGER
    statements = [
        # coupon.py models
        "ALTER TABLE coupon_ratings ALTER COLUMN seller_id TYPE INTEGER USING seller_id::INTEGER;",
        "ALTER TABLE coupon_ratings ALTER COLUMN buyer_id TYPE INTEGER USING buyer_id::INTEGER;",
        "ALTER TABLE user_favorites ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;",
        "ALTER TABLE coupons ALTER COLUMN seller_id TYPE INTEGER USING seller_id::INTEGER;",

        # order.py models
        "ALTER TABLE auction_bids ALTER COLUMN bidder_id TYPE INTEGER USING bidder_id::INTEGER;",
        "ALTER TABLE auctions ALTER COLUMN winner_id TYPE INTEGER USING winner_id::INTEGER;",
        "ALTER TABLE auctions ALTER COLUMN seller_id TYPE INTEGER USING seller_id::INTEGER;",
        "ALTER TABLE orders ALTER COLUMN resolved_by_admin_id TYPE INTEGER USING resolved_by_admin_id::INTEGER;",
        "ALTER TABLE orders ALTER COLUMN seller_id TYPE INTEGER USING seller_id::INTEGER;",
        "ALTER TABLE orders ALTER COLUMN buyer_id TYPE INTEGER USING buyer_id::INTEGER;",

        # user.py models
        "ALTER TABLE fund_locks ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;",
        "ALTER TABLE transactions ALTER COLUMN processed_by_admin_id TYPE INTEGER USING processed_by_admin_id::INTEGER;",
        "ALTER TABLE transactions ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;",
        "ALTER TABLE wallets ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;",
        "ALTER TABLE seller_profiles ALTER COLUMN verified_by_admin_id TYPE INTEGER USING verified_by_admin_id::INTEGER;",
        "ALTER TABLE seller_profiles ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;",
    ]

    for stmt in statements:
        op.execute(stmt)

    # החזרת ה-sequence ל-INT
    op.execute("ALTER SEQUENCE users_id_seq AS INTEGER;")

    # החזרת ה-PK לטיפוס INTEGER
    op.execute(
        """
        ALTER TABLE users 
        ALTER COLUMN id 
        TYPE INTEGER 
        USING id::INTEGER;
        """
    )

