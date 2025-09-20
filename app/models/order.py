"""
מודלי הזמנות ומכרזים - Orders, Auctions
עם תמיכה מלאה במחלוקות, holds וניהול זמנים
"""

import enum
from datetime import datetime, timezone, timedelta
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

class OrderStatus(enum.Enum):
    """סטטוס הזמנה - עדכון לפי הדרישות החדשות"""
    PENDING = "pending"           # ממתין לתשלום
    PAID = "paid"                 # שולם, ממתין לאספקה
    DELIVERED = "delivered"       # נמסר, חלון דיווח פתוח
    IN_DISPUTE = "in_dispute"     # במחלוקת
    RESOLVED = "resolved"         # מחלוקת נפתרה
    RELEASED = "released"         # כספים שוחררו למוכר
    CANCELLED = "cancelled"       # בוטל
    REFUNDED = "refunded"         # הוחזר


class DisputeReason(enum.Enum):
    """סיבות למחלוקת"""
    COUPON_INVALID = "coupon_invalid"         # קופון לא תקין
    COUPON_EXPIRED = "coupon_expired"         # קופון פג תוקף
    COUPON_USED = "coupon_used"               # קופון כבר נוצל
    WRONG_DETAILS = "wrong_details"           # פרטים שגויים
    SELLER_UNRESPONSIVE = "seller_unresponsive"  # מוכר לא מגיב
    OTHER = "other"                           # אחר


class AuctionStatus(enum.Enum):
    """סטטוס מכרז"""
    ACTIVE = "active"             # פעיל
    ENDED = "ended"               # הסתיים
    CANCELLED = "cancelled"       # בוטל
    FINALIZED = "finalized"       # סופי (תשלום בוצע)


# === Models ===

class Order(Base):
    """הזמנת קופון - עם תמיכה מלאה במחלוקות וטיימרים"""
    __tablename__ = "orders"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default_factory=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Participants
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"))
    
    # Order Details (ללא ברירות מחדל קודם)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # מחיר יחידה
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # סה"כ לפני עמלות
    
    # Financial Breakdown - שדות חובה לפני שדות עם ברירת מחדל
    seller_amount_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # סכום מוכר ברוטו (לפני עמלה)
    seller_amount_net: Mapped[Decimal] = mapped_column(Numeric(12, 2))    # סכום מוכר נטו (אחרי עמלה)
    
    
    # Status & Timing - תוספות חדשות קריטיות
    
    # Timing Fields - חדש וחשוב!
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default_factory=lambda: datetime.now(timezone.utc),
        init=False
    )
    purchased_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # מתי בוצע התשלום
    
    dispute_window_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # purchased_at + 12h - חלון דיווח
    
    seller_hold_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # purchased_at + 24h - שחרור אוטומטי
    
    buyer_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # אישור מוקדם של הקונה
    
    # Dispute Management - חדש
    reported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_reason: Mapped[Optional[DisputeReason]] = mapped_column(
        ENUM(DisputeReason), nullable=True
    )
    dispute_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by_admin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Delivery Info (ללא ברירת מחדל)
    coupon_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # === Relationships ===
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="orders")
    resolved_by_admin: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[resolved_by_admin_id]
    )

    # שדות עם ברירת מחדל (סוף המחלקה עבור dataclass)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[OrderStatus] = mapped_column(ENUM(OrderStatus), default=OrderStatus.PENDING)
    delivery_method: Mapped[str] = mapped_column(String(50), default="digital")
    buyer_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))  # עמלת קונה
    seller_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))  # עמלת מוכר

    # Updated timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default_factory=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # Indexes - חדש וחשוב לביצועים!
    __table_args__ = (
        Index("idx_orders_buyer", "buyer_id"),
        Index("idx_orders_seller", "seller_id"),
        Index("idx_orders_coupon", "coupon_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_purchased_at", "purchased_at"),
        
        # אינדקסים קריטיים לטיימרים!
        Index("idx_orders_dispute_window", "dispute_window_until"),
        Index("idx_orders_seller_hold", "seller_hold_until"),
        Index("idx_orders_status_timers", "status", "dispute_window_until", "seller_hold_until"),
        
        Index("idx_orders_dispute", "status", "reported_at"),
        Index("idx_orders_created", "created_at"),
        CheckConstraint("total_amount > 0", name="chk_order_amount_positive"),
        CheckConstraint("quantity > 0", name="chk_order_quantity_positive"),
    )
    
    def is_dispute_window_open(self) -> bool:
        """בדיקה האם חלון הדיווח עדיין פתוח"""
        if not self.dispute_window_until:
            return False
        return datetime.now(timezone.utc) < self.dispute_window_until
    
    def should_auto_release(self) -> bool:
        """בדיקה האם צריך לשחרר hold אוטומטית"""
        if not self.seller_hold_until:
            return False
        if self.status == OrderStatus.IN_DISPUTE:
            return False
        return datetime.now(timezone.utc) >= self.seller_hold_until
    
    def can_report_dispute(self) -> bool:
        """בדיקה האם ניתן לדווח על מחלוקת"""
        return (
            self.status == OrderStatus.DELIVERED and 
            self.is_dispute_window_open() and
            not self.reported_at
        )
    
    def calculate_financials(self, buyer_fee_percent: float, seller_fee_percent: float):
        """חישוב פיננסי של ההזמנה"""
        self.buyer_fee = self.total_amount * Decimal(str(buyer_fee_percent / 100))
        self.seller_amount_gross = self.total_amount
        self.seller_fee = self.seller_amount_gross * Decimal(str(seller_fee_percent / 100))
        self.seller_amount_net = self.seller_amount_gross - self.seller_fee
    
    def set_purchase_timers(self):
        """הגדרת טיימרים לאחר רכישה"""
        now = datetime.now(timezone.utc)
        self.purchased_at = now
        self.dispute_window_until = now + timedelta(hours=12)
        self.seller_hold_until = now + timedelta(hours=24)
    
    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status={self.status.value}, amount={self.total_amount})>"


class Auction(Base):
    """מכרז קופון"""
    __tablename__ = "auctions"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default_factory=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Basic Info
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"))
    
    # Auction Settings
    starting_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    current_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reserve_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )  # מחיר מינימום
    
    # Timing
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extended_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # הארכה אוטומטית
    
    # Winner Info (ללא ברירת מחדל)
    winner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    winning_bid_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("auction_bids.id"), nullable=True
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # === Relationships ===
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="auctions")
    winner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[winner_id])
    bids: Mapped[list["AuctionBid"]] = relationship(
        "AuctionBid", back_populates="auction", cascade="all, delete-orphan"
    )
    winning_bid: Mapped[Optional["AuctionBid"]] = relationship(
        "AuctionBid", foreign_keys=[winning_bid_id]
    )
    
    # Status (עם ברירת מחדל) ושדות סטטיסטיים עם ברירת מחדל
    status: Mapped[AuctionStatus] = mapped_column(ENUM(AuctionStatus), default=AuctionStatus.ACTIVE)
    total_bids: Mapped[int] = mapped_column(Integer, default=0)
    unique_bidders: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
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

    # Indexes
    __table_args__ = (
        Index("idx_auctions_seller", "seller_id"),
        Index("idx_auctions_coupon", "coupon_id"),
        Index("idx_auctions_status", "status"),
        Index("idx_auctions_ends_at", "ends_at"),
        Index("idx_auctions_extended", "extended_until"),
        Index("idx_auctions_active", "status", "ends_at"),
        CheckConstraint("starting_price > 0", name="chk_auction_starting_price"),
        CheckConstraint("current_price >= starting_price", name="chk_auction_current_price"),
        CheckConstraint("ends_at > starts_at", name="chk_auction_timing"),
    )
    
    def is_active(self) -> bool:
        """בדיקה האם המכרז פעיל"""
        now = datetime.now(timezone.utc)
        end_time = self.extended_until or self.ends_at
        return (
            self.status == AuctionStatus.ACTIVE and
            self.starts_at <= now <= end_time
        )
    
    def should_extend(self, bid_time: datetime, extension_minutes: int = 10) -> bool:
        """בדיקה האם צריך להאריך המכרז"""
        if not self.is_active():
            return False
        
        end_time = self.extended_until or self.ends_at
        time_left = (end_time - bid_time).total_seconds() / 60
        return time_left <= extension_minutes
    
    def extend_auction(self, extension_minutes: int = 10):
        """הארכת המכרז"""
        now = datetime.now(timezone.utc)
        self.extended_until = now + timedelta(minutes=extension_minutes)
    
    def __repr__(self) -> str:
        return f"<Auction(id={self.id}, status={self.status.value}, current_price={self.current_price})>"


class AuctionBid(Base):
    """הצעה במכרז"""
    __tablename__ = "auction_bids"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default_factory=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Foreign Keys
    auction_id: Mapped[str] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"))
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Bid Details
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_winning: Mapped[bool] = mapped_column(Boolean, default=False)
    is_outbid: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Fund Lock Reference
    fund_lock_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("fund_locks.id"), nullable=True
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default_factory=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # === Relationships ===
    auction: Mapped["Auction"] = relationship("Auction", back_populates="bids")
    bidder: Mapped["User"] = relationship("User")
    fund_lock: Mapped[Optional["FundLock"]] = relationship("FundLock")
    
    # Indexes
    __table_args__ = (
        Index("idx_bids_auction", "auction_id"),
        Index("idx_bids_bidder", "bidder_id"),
        Index("idx_bids_amount", "amount"),
        Index("idx_bids_winning", "is_winning"),
        Index("idx_bids_auction_amount", "auction_id", "amount"),
        Index("idx_bids_created", "created_at"),
        CheckConstraint("amount > 0", name="chk_bid_amount_positive"),
    )
    
    def __repr__(self) -> str:
        return f"<AuctionBid(id={self.id}, amount={self.amount}, winning={self.is_winning})>"


# === Order Management Functions ===

def create_purchase_order(
    buyer_id: int,
    seller_id: int, 
    coupon_id: str,
    unit_price: Decimal,
    quantity: int = 1,
    buyer_fee_percent: float = 2.0,
    seller_fee_percent: float = 5.0
) -> Order:
    """יצירת הזמנת רכישה חדשה"""
    total_amount = unit_price * quantity
    
    order = Order(
        buyer_id=buyer_id,
        seller_id=seller_id,
        coupon_id=coupon_id,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        status=OrderStatus.PENDING
    )
    
    # חישוב פיננסי
    order.calculate_financials(buyer_fee_percent, seller_fee_percent)
    
    return order


def create_auction_order(auction: Auction, winning_bid: AuctionBid) -> Order:
    """יצירת הזמנה ממכרז שהסתיים"""
    order = create_purchase_order(
        buyer_id=winning_bid.bidder_id,
        seller_id=auction.seller_id,
        coupon_id=auction.coupon_id,
        unit_price=winning_bid.amount,
        quantity=1
    )
    
    # סימון שמקורו מכרז
    order.metadata = f"auction:{auction.id}"
    
    return order


# === Status Transition Functions ===

def mark_order_paid(order: Order) -> None:
    """סימון הזמנה כמשולמת והגדרת טיימרים"""
    order.status = OrderStatus.PAID
    order.purchased_at = datetime.now(timezone.utc)


def mark_order_delivered(order: Order, coupon_data: str) -> None:
    """סימון הזמנה כנמסרת והפעלת חלון דיווח"""
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(timezone.utc)
    order.coupon_data = coupon_data
    order.set_purchase_timers()  # הגדרת טיימרים ל-12h ו-24h


def buyer_confirm_order(order: Order) -> None:
    """אישור מוקדם של הקונה"""
    order.buyer_confirmed_at = datetime.now(timezone.utc)
    order.status = OrderStatus.RELEASED
    # TODO: שחרור hold מיידי למוכר


def report_dispute(
    order: Order, 
    reason: DisputeReason, 
    description: str
) -> None:
    """דיווח על מחלוקת"""
    if not order.can_report_dispute():
        raise ValueError("Cannot report dispute - window closed or already reported")
    
    order.status = OrderStatus.IN_DISPUTE
    order.reported_at = datetime.now(timezone.utc)
    order.dispute_reason = reason
    order.dispute_description = description


def resolve_dispute(
    order: Order,
    admin_id: int,
    resolution_notes: str,
    refund_buyer: bool = False,
    partial_refund_amount: Optional[Decimal] = None
) -> None:
    """פתרון מחלוקת על ידי אדמין"""
    order.status = OrderStatus.RESOLVED
    order.resolved_at = datetime.now(timezone.utc)
    order.resolved_by_admin_id = admin_id
    order.resolution_notes = resolution_notes
    
    # TODO: ביצוע החזרים או שחרור כספים לפי ההחלטה


# === Scheduler Helper Functions ===

def get_orders_for_dispute_window_close() -> list[str]:
    """
    קבלת הזמנות שחלון הדיווח שלהן נסגר
    לשימוש ב-Scheduler
    """
    # TODO: SQL Query לקבלת הזמנות עם dispute_window_until < now
    # AND status = DELIVERED AND reported_at IS NULL
    pass


def get_orders_for_hold_release() -> list[str]:
    """
    קבלת הזמנות שצריכות שחרור hold
    לשימוש ב-Scheduler
    """
    # TODO: SQL Query לקבלת הזמנות עם seller_hold_until < now
    # AND status NOT IN (IN_DISPUTE, RELEASED) 
    pass


def get_ending_auctions(minutes_ahead: int = 120) -> list[str]:
    """
    קבלת מכרזים שמסתיימים בקרוב
    לשימוש בהתראות
    """
    # TODO: SQL Query לקבלת מכרזים שמסתיימים בזמן הקרוב
    pass


# TODO: הוספת Escrow Management
"""
עתיד - Escrow & Payment Processing:
- EscrowAccount model
- PaymentProvider integration  
- Real-time payment webhooks
- Automatic settlement
- Multi-currency support
- Payment method management
"""
