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
    # Enum types (ensure existence before tables)
    conn.execute(text(
        """
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('BUYER','SELLER','ADMIN');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE verificationstatus AS ENUM ('UNVERIFIED','PENDING','VERIFIED','REJECTED');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE transactiontype AS ENUM (
                'DEPOSIT','WITHDRAWAL','PURCHASE_DEBIT','SALE_CREDIT','REFUND','FEE_DEBIT','SYSTEM_ADJUSTMENT',
                'LOCK','RELEASE','HOLD_LOCK','HOLD_RELEASE'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE orderstatus AS ENUM ('PENDING','PAID','DELIVERED','IN_DISPUTE','RESOLVED','RELEASED','CANCELLED','REFUNDED');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE auctionstatus AS ENUM ('ACTIVE','ENDED','CANCELLED','FINALIZED');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE coupontype AS ENUM ('REGULAR','AUCTION','BOTH');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE couponstatus AS ENUM ('DRAFT','ACTIVE','SOLD','EXPIRED','SUSPENDED','DELETED');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        DO $$ BEGIN
            CREATE TYPE disputereason AS ENUM ('COUPON_INVALID','COUPON_EXPIRED','COUPON_USED','WRONG_DETAILS','SELLER_UNRESPONSIVE','OTHER');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    ))
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

    # coupon_categories
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS coupon_categories (
            id VARCHAR(50) PRIMARY KEY,
            name_he VARCHAR(100) NOT NULL,
            name_en VARCHAR(100),
            description TEXT,
            icon_emoji VARCHAR(10) DEFAULT '🎁',
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            coupon_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_categories_active ON coupon_categories (is_active);
        CREATE INDEX IF NOT EXISTS idx_categories_sort ON coupon_categories (sort_order);
        """
    ))

    # coupons
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS coupons (
            id VARCHAR(36) PRIMARY KEY,
            seller_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            category_id VARCHAR(50) REFERENCES coupon_categories(id),
            expires_at TIMESTAMPTZ,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            business_name VARCHAR(200) NOT NULL,
            original_price NUMERIC(10,2) NOT NULL,
            selling_price NUMERIC(10,2) NOT NULL,
            discount_percent INTEGER,
            valid_from TIMESTAMPTZ,
            valid_until TIMESTAMPTZ,
            terms_and_conditions TEXT,
            usage_instructions TEXT,
            restrictions TEXT,
            coupon_code VARCHAR(100),
            qr_code_data TEXT,
            barcode_data VARCHAR(100),
            image_urls TEXT[],
            location_city VARCHAR(100),
            location_address VARCHAR(300),
            admin_notes TEXT,
            published_at TIMESTAMPTZ,
            coupon_type VARCHAR(50) DEFAULT 'regular',
            status VARCHAR(50) DEFAULT 'draft',
            quantity INTEGER DEFAULT 1,
            quantity_sold INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            favorite_count INTEGER DEFAULT 0,
            inquiry_count INTEGER DEFAULT 0,
            is_featured BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT chk_coupon_original_price CHECK (original_price > 0),
            CONSTRAINT chk_coupon_selling_price CHECK (selling_price > 0),
            CONSTRAINT chk_coupon_quantity CHECK (quantity >= 0),
            CONSTRAINT chk_coupon_quantity_sold CHECK (quantity_sold >= 0),
            CONSTRAINT chk_coupon_quantity_logic CHECK (quantity_sold <= quantity)
        );
        CREATE INDEX IF NOT EXISTS idx_coupons_seller ON coupons (seller_id);
        CREATE INDEX IF NOT EXISTS idx_coupons_category ON coupons (category_id);
        CREATE INDEX IF NOT EXISTS idx_coupons_status ON coupons (status);
        CREATE INDEX IF NOT EXISTS idx_coupons_type ON coupons (coupon_type);
        CREATE INDEX IF NOT EXISTS idx_coupons_price ON coupons (selling_price);
        CREATE INDEX IF NOT EXISTS idx_coupons_expires ON coupons (expires_at);
        CREATE INDEX IF NOT EXISTS idx_coupons_published ON coupons (published_at);
        CREATE INDEX IF NOT EXISTS idx_coupons_featured ON coupons (is_featured);
        CREATE INDEX IF NOT EXISTS idx_coupons_location ON coupons (location_city);
        CREATE INDEX IF NOT EXISTS idx_coupons_search ON coupons (status, category_id, selling_price);
        CREATE INDEX IF NOT EXISTS idx_coupons_active ON coupons (status, expires_at, quantity);
        """
    ))

    # orders
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id VARCHAR(36) PRIMARY KEY,
            buyer_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            seller_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            coupon_id VARCHAR(36) REFERENCES coupons(id) ON DELETE CASCADE,
            unit_price NUMERIC(10,2) NOT NULL,
            total_amount NUMERIC(12,2) NOT NULL,
            seller_amount_gross NUMERIC(12,2) NOT NULL,
            seller_amount_net NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            purchased_at TIMESTAMPTZ,
            dispute_window_until TIMESTAMPTZ,
            seller_hold_until TIMESTAMPTZ,
            buyer_confirmed_at TIMESTAMPTZ,
            reported_at TIMESTAMPTZ,
            dispute_reason VARCHAR(50),
            dispute_description TEXT,
            resolved_by_admin_id BIGINT REFERENCES users(id),
            resolved_at TIMESTAMPTZ,
            resolution_notes TEXT,
            coupon_data TEXT,
            delivered_at TIMESTAMPTZ,
            quantity INTEGER DEFAULT 1,
            status VARCHAR(50) DEFAULT 'pending',
            delivery_method VARCHAR(50) DEFAULT 'digital',
            buyer_fee NUMERIC(10,2) DEFAULT 0.00,
            seller_fee NUMERIC(10,2) DEFAULT 0.00,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT chk_order_amount_positive CHECK (total_amount > 0),
            CONSTRAINT chk_order_quantity_positive CHECK (quantity > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders (buyer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders (seller_id);
        CREATE INDEX IF NOT EXISTS idx_orders_coupon ON orders (coupon_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
        CREATE INDEX IF NOT EXISTS idx_orders_purchased_at ON orders (purchased_at);
        CREATE INDEX IF NOT EXISTS idx_orders_dispute_window ON orders (dispute_window_until);
        CREATE INDEX IF NOT EXISTS idx_orders_seller_hold ON orders (seller_hold_until);
        CREATE INDEX IF NOT EXISTS idx_orders_status_timers ON orders (status, dispute_window_until, seller_hold_until);
        CREATE INDEX IF NOT EXISTS idx_orders_dispute ON orders (status, reported_at);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders (created_at);
        """
    ))

    # auctions (without FK for winning_bid_id to avoid circular creation)
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS auctions (
            id VARCHAR(36) PRIMARY KEY,
            seller_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            coupon_id VARCHAR(36) REFERENCES coupons(id) ON DELETE CASCADE,
            starting_price NUMERIC(10,2) NOT NULL,
            current_price NUMERIC(10,2) NOT NULL,
            reserve_price NUMERIC(10,2),
            starts_at TIMESTAMPTZ NOT NULL,
            ends_at TIMESTAMPTZ NOT NULL,
            extended_until TIMESTAMPTZ,
            winner_id BIGINT REFERENCES users(id),
            winning_bid_id VARCHAR(36),
            finalized_at TIMESTAMPTZ,
            status VARCHAR(50) DEFAULT 'active',
            total_bids INTEGER DEFAULT 0,
            unique_bidders INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT chk_auction_starting_price CHECK (starting_price > 0),
            CONSTRAINT chk_auction_current_price CHECK (current_price >= starting_price),
            CONSTRAINT chk_auction_timing CHECK (ends_at > starts_at)
        );
        CREATE INDEX IF NOT EXISTS idx_auctions_seller ON auctions (seller_id);
        CREATE INDEX IF NOT EXISTS idx_auctions_coupon ON auctions (coupon_id);
        CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions (status);
        CREATE INDEX IF NOT EXISTS idx_auctions_ends_at ON auctions (ends_at);
        CREATE INDEX IF NOT EXISTS idx_auctions_extended ON auctions (extended_until);
        CREATE INDEX IF NOT EXISTS idx_auctions_active ON auctions (status, ends_at);
        """
    ))

    # auction_bids
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS auction_bids (
            id VARCHAR(36) PRIMARY KEY,
            auction_id VARCHAR(36) REFERENCES auctions(id) ON DELETE CASCADE,
            bidder_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            fund_lock_id VARCHAR(36) REFERENCES fund_locks(id),
            amount NUMERIC(10,2) NOT NULL,
            is_winning BOOLEAN DEFAULT FALSE,
            is_outbid BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT chk_bid_amount_positive CHECK (amount > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_bids_auction ON auction_bids (auction_id);
        CREATE INDEX IF NOT EXISTS idx_bids_bidder ON auction_bids (bidder_id);
        CREATE INDEX IF NOT EXISTS idx_bids_amount ON auction_bids (amount);
        CREATE INDEX IF NOT EXISTS idx_bids_winning ON auction_bids (is_winning);
        CREATE INDEX IF NOT EXISTS idx_bids_auction_amount ON auction_bids (auction_id, amount);
        CREATE INDEX IF NOT EXISTS idx_bids_created ON auction_bids (created_at);
        """
    ))

    # user_favorites
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS user_favorites (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            coupon_id VARCHAR(36) REFERENCES coupons(id) ON DELETE CASCADE,
            original_price NUMERIC(10,2) NOT NULL,
            last_price_check TIMESTAMPTZ,
            notify_price_drop BOOLEAN DEFAULT TRUE,
            notify_similar BOOLEAN DEFAULT FALSE,
            notify_expiry BOOLEAN DEFAULT TRUE,
            price_alerts_sent INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_user_coupon_favorite UNIQUE (user_id, coupon_id)
        );
        CREATE INDEX IF NOT EXISTS idx_favorites_user ON user_favorites (user_id);
        CREATE INDEX IF NOT EXISTS idx_favorites_coupon ON user_favorites (coupon_id);
        CREATE INDEX IF NOT EXISTS idx_favorites_notifications ON user_favorites (notify_price_drop, notify_expiry);
        """
    ))

    # coupon_ratings
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS coupon_ratings (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(36) REFERENCES orders(id) ON DELETE CASCADE,
            buyer_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            seller_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            coupon_id VARCHAR(36) REFERENCES coupons(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL,
            comment VARCHAR(150),
            is_public BOOLEAN DEFAULT TRUE,
            is_verified_purchase BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_rating_per_order UNIQUE (order_id),
            CONSTRAINT chk_rating_range CHECK (rating >= 1 AND rating <= 5),
            CONSTRAINT chk_comment_length CHECK (char_length(comment) <= 150)
        );
        CREATE INDEX IF NOT EXISTS idx_ratings_seller ON coupon_ratings (seller_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_coupon ON coupon_ratings (coupon_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_buyer ON coupon_ratings (buyer_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_rating ON coupon_ratings (rating);
        CREATE INDEX IF NOT EXISTS idx_ratings_created ON coupon_ratings (created_at);
        """
    ))


def downgrade() -> None:
    conn = op.get_bind()
    # Drop in reverse dependency order
    conn.execute(text("DROP TABLE IF EXISTS coupon_ratings CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS user_favorites CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS auction_bids CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS auctions CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS coupons CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS coupon_categories CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS fund_locks CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS transactions CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS seller_profiles CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS wallets CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
    # Drop enum types
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS disputereason; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS couponstatus; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS coupontype; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS auctionstatus; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS orderstatus; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS transactiontype; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS verificationstatus; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))
    conn.execute(text("DO $$ BEGIN DROP TYPE IF EXISTS userrole; EXCEPTION WHEN undefined_object THEN NULL; END $$;"))

