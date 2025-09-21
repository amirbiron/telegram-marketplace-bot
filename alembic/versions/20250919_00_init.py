"""init: create base tables

Revision ID: 20250919_00
Revises: 
Create Date: 2025-09-19
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20250919_00"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    יצירת כל הטבלאות ההתחלתיות לפי ה-metadata.
    אנו משתמשים ב-execute על קוד SQL שמייצר Alembic ממודלים, אך כיוון שאין כאן
    target_metadata, נשתמש ב-Base.metadata.create_all באמצעות פקודת SQL.
    כדי לשמור פשטות ובשביל סביבת בדיקות, נקרא לפונקציה שמייצרת טבלאות.
    """
    # חשוב: ב-run-time של Alembic אין גישה נוחה ל-Base.metadata.create_all ללא target_metadata.
    # לכן ניצור טבלאות נדרשות ידנית ב-SQL מינימלי, רק את טבלת users הדרושה למיגרציות הבאות.
    conn = op.get_bind()
    # users
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            telegram_user_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(100),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(200),
            last_activity_at TIMESTAMPTZ,
            role VARCHAR(20) NOT NULL DEFAULT 'buyer',
            is_active BOOLEAN DEFAULT TRUE,
            is_blocked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_user_id);
        CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
        CREATE INDEX IF NOT EXISTS idx_users_active ON users (is_active);
        CREATE INDEX IF NOT EXISTS idx_users_created ON users (created_at);
        """
    ))

    # wallets
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            total_balance NUMERIC(12,2) DEFAULT 0.00,
            locked_balance NUMERIC(12,2) DEFAULT 0.00,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT chk_total_balance_positive CHECK (total_balance >= 0),
            CONSTRAINT chk_locked_balance_positive CHECK (locked_balance >= 0),
            CONSTRAINT chk_locked_within_total CHECK (locked_balance <= total_balance)
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallets (user_id);
        CREATE INDEX IF NOT EXISTS idx_wallet_balances ON wallets (total_balance, locked_balance);
        """
    ))

    # seller_profiles
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS seller_profiles (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            business_name VARCHAR(200) NOT NULL DEFAULT '',
            description TEXT,
            verification_documents JSONB NOT NULL DEFAULT '[]',
            verified_at TIMESTAMPTZ,
            verified_by_admin_id BIGINT REFERENCES users(id),
            average_rating NUMERIC(3,2) NOT NULL DEFAULT 0.00,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
            daily_quota INTEGER DEFAULT 10,
            daily_count INTEGER DEFAULT 0,
            quota_reset_date TIMESTAMPTZ DEFAULT NOW(),
            total_sales INTEGER DEFAULT 0,
            total_ratings INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_seller_verified ON seller_profiles (is_verified);
        CREATE INDEX IF NOT EXISTS idx_seller_status ON seller_profiles (verification_status);
        CREATE INDEX IF NOT EXISTS idx_seller_quota_reset ON seller_profiles (quota_reset_date);
        CREATE INDEX IF NOT EXISTS idx_seller_rating ON seller_profiles (average_rating);
        """
    ))

    # transactions
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id VARCHAR(36) PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            description VARCHAR(500) NOT NULL,
            reference_type VARCHAR(50),
            reference_id VARCHAR(100),
            balance_before NUMERIC(12,2) NOT NULL,
            balance_after NUMERIC(12,2) NOT NULL,
            extra_metadata TEXT,
            processed_by_admin_id BIGINT REFERENCES users(id),
            locked_before NUMERIC(12,2) DEFAULT 0.00,
            locked_after NUMERIC(12,2) DEFAULT 0.00,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions (user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_wallet ON transactions (wallet_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (type);
        CREATE INDEX IF NOT EXISTS idx_transactions_reference ON transactions (reference_type, reference_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions (created_at);
        CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions (amount);
        """
    ))

    # fund_locks
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS fund_locks (
            id VARCHAR(36) PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE,
            amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
            reason VARCHAR(200) NOT NULL,
            reference_type VARCHAR(50) NOT NULL,
            reference_id VARCHAR(100) NOT NULL,
            expires_at TIMESTAMPTZ,
            released_at TIMESTAMPTZ,
            is_active BOOLEAN DEFAULT TRUE,
            locked_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_fund_locks_user ON fund_locks (user_id);
        CREATE INDEX IF NOT EXISTS idx_fund_locks_wallet ON fund_locks (wallet_id);
        CREATE INDEX IF NOT EXISTS idx_fund_locks_reference ON fund_locks (reference_type, reference_id);
        CREATE INDEX IF NOT EXISTS idx_fund_locks_active ON fund_locks (is_active);
        CREATE INDEX IF NOT EXISTS idx_fund_locks_expires ON fund_locks (expires_at);
        """
    ))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS users CASCADE;"))

