"""
מודלי משתמשים - Users, Wallets, Transactions
עם תמיכה מלאה ביתרות, נעילות כספים ו-Ledger מתקדם
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Numeric, Text,
    ForeignKey, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM
import uuid

from app.database import Base


# === Enums ===

class UserRole(enum.Enum):
    """תפקידי משתמש"""
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"


class TransactionType(enum.Enum):
    """סוגי תנועות כספיות - Ledger מתקדם"""
    DEPOSIT = "deposit"           # הפקדה
    WITHDRAWAL = "withdrawal"     # משיכה
    PURCHASE_DEBIT = "purchase_debit"    # חיוב קנייה (כולל עמלה)
    SALE_CREDIT = "sale_credit"          # זיכוי מכירה (נטו)
    REFUND = "refund"             # החזר
    FEE_DEBIT = "fee_debit"       # חיוב עמלה
    SYSTEM_ADJUSTMENT = "system_adjustment"  # תיקון מערכת
    
    # סוגים חדשים לנעילות
    LOCK = "lock"                 # נעילת כספים (מכרז/הזמנה)
    RELEASE = "release"           # שחרור נעילה
    HOLD_LOCK = "hold_lock"       # נעילה למוכר עד שחרור
    HOLD_RELEASE = "hold_release" # שחרור hold למוכר


class VerificationStatus(enum.Enum):
    """סטטוס אימות מוכר"""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# === Models ===

class User(Base):
    """משתמש במערכת"""
    __tablename__ = "users"
    
    # Basic Info
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Role & Status
    role: Mapped[UserRole] = mapped_column(ENUM(UserRole), default=UserRole.BUYER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps - שדה ללא ברירת מחדל לפני שדות עם ברירת מחדל
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default_factory=lambda: datetime.now(timezone.utc),
        init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default_factory=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # Contact Info (עבור מוכרים)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # === Relationships ===
    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    seller_profile: Mapped[Optional["SellerProfile"]] = relationship(
        "SellerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    fund_locks: Mapped[list["FundLock"]] = relationship(
        "FundLock", back_populates="user", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_user_id"),
        Index("idx_users_role", "role"),
        Index("idx_users_active", "is_active"),
        Index("idx_users_created", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_user_id}, role={self.role.value})>"


class SellerProfile(Base):
    """פרופיל מוכר עם אימות וגבלות"""
    __tablename__ = "seller_profiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Business Info
    business_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Verification - תוספות חדשות
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        ENUM(VerificationStatus), 
        default=VerificationStatus.UNVERIFIED
    )
    verification_documents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_admin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    # Daily Limits - חדש
    daily_quota: Mapped[int] = mapped_column(Integer, default=10)  # 10 קופונים לליא מאומת
    daily_count: Mapped[int] = mapped_column(Integer, default=0)   # מונה נוכחי
    quota_reset_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    
    # Stats & Rating
    total_sales: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True  # 0.00 - 5.00
    )
    total_ratings: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="seller_profile")
    
    # Indexes
    __table_args__ = (
        Index("idx_seller_verified", "is_verified"),
        Index("idx_seller_status", "verification_status"),
        Index("idx_seller_quota_reset", "quota_reset_date"),
        Index("idx_seller_rating", "average_rating"),
    )
    
    def can_upload_coupon(self) -> bool:
        """בדיקה האם המוכר יכול להעלות קופון נוסף"""
        # אם מאומת - ללא הגבלה
        if self.is_verified:
            return True
        
        # בדיקה אם צריך לאפס מונה יומי
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        if self.quota_reset_date < today:
            return True  # יאופס במקום אחר
        
        return self.daily_count < self.daily_quota
    
    def __repr__(self) -> str:
        return f"<SellerProfile(user_id={self.user_id}, verified={self.is_verified})>"


class Wallet(Base):
    """ארנק משתמש עם יתרות ונעילות"""
    __tablename__ = "wallets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    
    # יתרות - עדכון לפי הדרישות החדשות
    total_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal('0.00')
    )  # 💰 יתרה כוללת
    locked_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal('0.00')
    )  # 🔒 יתרה קפואה (מכרזים + holds)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="wallet", cascade="all, delete-orphan"
    )
    fund_locks: Mapped[list["FundLock"]] = relationship(
        "FundLock", back_populates="wallet", cascade="all, delete-orphan"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint("total_balance >= 0", name="chk_total_balance_positive"),
        CheckConstraint("locked_balance >= 0", name="chk_locked_balance_positive"),
        CheckConstraint("locked_balance <= total_balance", name="chk_locked_within_total"),
        Index("idx_wallet_user", "user_id"),
        Index("idx_wallet_balances", "total_balance", "locked_balance"),
    )
    
    @property
    def available_balance(self) -> Decimal:
        """✅ יתרה זמינה = כוללת - קפואה"""
        return self.total_balance - self.locked_balance
    
    def can_afford(self, amount: Decimal) -> bool:
        """בדיקה האם יש יתרה זמינה מספקת"""
        return self.available_balance >= amount
    
    def __repr__(self) -> str:
        return f"<Wallet(user_id={self.user_id}, total={self.total_balance}, locked={self.locked_balance})>"


class Transaction(Base):
    """רשומת תנועה כספית - Ledger מלא"""
    __tablename__ = "transactions"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Foreign Keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    
    # Transaction Details
    type: Mapped[TransactionType] = mapped_column(ENUM(TransactionType))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # חיובי/שלילי
    description: Mapped[str] = mapped_column(String(500))
    
    # References
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "order", "auction", etc.
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Balances After Transaction
    balance_before: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    locked_before: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal('0.00'))
    locked_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal('0.00'))
    
    # Metadata
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON נוסף
    processed_by_admin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        Index("idx_transactions_user", "user_id"),
        Index("idx_transactions_wallet", "wallet_id"),
        Index("idx_transactions_type", "type"),
        Index("idx_transactions_reference", "reference_type", "reference_id"),
        Index("idx_transactions_created", "created_at"),
        Index("idx_transactions_amount", "amount"),
    )
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, type={self.type.value}, amount={self.amount})>"


class FundLock(Base):
    """נעילות כספים - למכרזים והזמנות"""
    __tablename__ = "fund_locks"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Foreign Keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    
    # Lock Details
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(200))  # "auction_bid", "order_hold", etc.
    
    # References
    reference_type: Mapped[str] = mapped_column(String(50))  # "auction", "order"
    reference_id: Mapped[str] = mapped_column(String(100))
    
    # Status & Timing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Timestamps
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        init=False
    )
    released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="fund_locks")
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="fund_locks")
    
    # Indexes
    __table_args__ = (
        Index("idx_fund_locks_user", "user_id"),
        Index("idx_fund_locks_wallet", "wallet_id"),
        Index("idx_fund_locks_reference", "reference_type", "reference_id"),
        Index("idx_fund_locks_active", "is_active"),
        Index("idx_fund_locks_expires", "expires_at"),
        CheckConstraint("amount > 0", name="chk_lock_amount_positive"),
    )
    
    def is_expired(self) -> bool:
        """בדיקה האם הנעילה פגה"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def __repr__(self) -> str:
        return f"<FundLock(id={self.id}, amount={self.amount}, active={self.is_active})>"


# === Utility Functions ===

async def create_user_wallet(user: User) -> Wallet:
    """יצירת ארנק חדש למשתמש"""
    wallet = Wallet(
        user_id=user.id,
        total_balance=Decimal('0.00'),
        locked_balance=Decimal('0.00')
    )
    return wallet


def calculate_fees(amount: Decimal, is_buyer: bool = True, seller_verified: bool = False) -> tuple[Decimal, Decimal]:
    """
    חישוב עמלות
    Returns: (עמלת קונה, עמלת מוכר)
    """
    from app.config import settings
    
    buyer_fee = Decimal('0.00')
    seller_fee = Decimal('0.00')
    
    if is_buyer:
        buyer_fee = amount * (Decimal(str(settings.BUYER_FEE_PERCENT)) / Decimal('100'))
    
    if seller_verified:
        seller_fee = amount * (Decimal(str(settings.SELLER_VERIFIED_FEE_PERCENT)) / Decimal('100'))
    else:
        seller_fee = amount * (Decimal(str(settings.SELLER_UNVERIFIED_FEE_PERCENT)) / Decimal('100'))
    
    return buyer_fee, seller_fee
