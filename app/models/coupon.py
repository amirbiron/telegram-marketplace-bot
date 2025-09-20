"""
מודלי קופונים וקטגוריות - Coupons, Categories, Favorites
עם תמיכה במכרזים, מועדפים והתראות
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
from sqlalchemy.dialects.postgresql import UUID, ENUM, ARRAY
import uuid

from app.database import Base


# === Enums ===

class CouponType(enum.Enum):
    """סוג קופון"""
    REGULAR = "regular"           # קופון רגיל
    AUCTION = "auction"           # קופון למכרז
    BOTH = "both"                 # ניתן לשני הסוגים


class CouponStatus(enum.Enum):
    """סטטוס קופון"""
    DRAFT = "draft"               # טיוטה
    ACTIVE = "active"             # פעיל
    SOLD = "sold"                 # נמכר
    EXPIRED = "expired"           # פג תוקף
    SUSPENDED = "suspended"       # הושעה על ידי אדמין
    DELETED = "deleted"           # נמחק


class NotificationType(enum.Enum):
    """סוגי התראות"""
    PRICE_DROP = "price_drop"             # ירידת מחיר
    SIMILAR_COUPON = "similar_coupon"     # קופון דומה
    EXPIRY_WARNING = "expiry_warning"     # אזהרת פקיעה
    BACK_IN_STOCK = "back_in_stock"       # חזר למלאי


# === Models ===

class CouponCategory(Base):
    """קטגוריות קופונים"""
    __tablename__ = "coupon_categories"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # "food", "fashion", etc.
    # === Relationships ===
    coupons: Mapped[list["Coupon"]] = relationship(
        "Coupon", back_populates="category", cascade="all, delete-orphan"
    )
    name_he: Mapped[str] = mapped_column(String(100))  # "🍕 מסעדות ואוכל"
    name_en: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_emoji: Mapped[str] = mapped_column(String(10), default="🎁")
    
    # Ordering & Display
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Stats
    coupon_count: Mapped[int] = mapped_column(Integer, default=0)
    
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
    
    
    
    # Indexes
    __table_args__ = (
        Index("idx_categories_active", "is_active"),
        Index("idx_categories_sort", "sort_order"),
    )
    
    def __repr__(self) -> str:
        return f"<CouponCategory(id={self.id}, name={self.name_he})>"


class Coupon(Base):
    """קופון/כרטיס למכירה"""
    __tablename__ = "coupons"
    
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4()),
        init=False
    )
    
    # Basic Info
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[str] = mapped_column(ForeignKey("coupon_categories.id"))
    
    # Content
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    business_name: Mapped[str] = mapped_column(String(200))  # שם העסק
    
    # Pricing
    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # מחיר רשמי
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))   # מחיר מכירה
    discount_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # אחוז הנחה
    
    # Type & Availability
    coupon_type: Mapped[CouponType] = mapped_column(
        ENUM(CouponType), 
        default=CouponType.REGULAR
    )
    status: Mapped[CouponStatus] = mapped_column(
        ENUM(CouponStatus), 
        default=CouponStatus.DRAFT
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    quantity_sold: Mapped[int] = mapped_column(Integer, default=0)
    
    # Validity
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Terms & Conditions
    terms_and_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Digital Content
    coupon_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    qr_code_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    barcode_data: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Media
    image_urls: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )  # רשימת תמונות
    
    # Location (אופציונלי)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    
    # Stats & Performance
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)
    inquiry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Admin Notes
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    
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
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # === Relationships ===
    seller: Mapped["User"] = relationship("User")
    category: Mapped["CouponCategory"] = relationship("CouponCategory", back_populates="coupons")
    
    # Orders & Auctions
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="coupon", cascade="all, delete-orphan"
    )
    auctions: Mapped[list["Auction"]] = relationship(
        "Auction", back_populates="coupon", cascade="all, delete-orphan"
    )
    
    # Favorites & Notifications
    favorites: Mapped[list["UserFavorite"]] = relationship(
        "UserFavorite", back_populates="coupon", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_coupons_seller", "seller_id"),
        Index("idx_coupons_category", "category_id"),
        Index("idx_coupons_status", "status"),
        Index("idx_coupons_type", "coupon_type"),
        Index("idx_coupons_price", "selling_price"),
        Index("idx_coupons_expires", "expires_at"),
        Index("idx_coupons_published", "published_at"),
        Index("idx_coupons_featured", "is_featured"),
        Index("idx_coupons_location", "location_city"),
        Index("idx_coupons_search", "status", "category_id", "selling_price"),
        Index("idx_coupons_active", "status", "expires_at", "quantity"),
        CheckConstraint("original_price > 0", name="chk_coupon_original_price"),
        CheckConstraint("selling_price > 0", name="chk_coupon_selling_price"),
        CheckConstraint("quantity >= 0", name="chk_coupon_quantity"),
        CheckConstraint("quantity_sold >= 0", name="chk_coupon_quantity_sold"),
        CheckConstraint("quantity_sold <= quantity", name="chk_coupon_quantity_logic"),
    )
    
    @property
    def is_available(self) -> bool:
        """בדיקה האם הקופון זמין לרכישה"""
        now = datetime.now(timezone.utc)
        return (
            self.status == CouponStatus.ACTIVE and
            self.quantity > self.quantity_sold and
            (not self.expires_at or self.expires_at > now) and
            (not self.valid_from or self.valid_from <= now)
        )
    
    @property
    def remaining_quantity(self) -> int:
        """כמות נותרת"""
        return max(0, self.quantity - self.quantity_sold)
    
    @property 
    def calculated_discount_percent(self) -> Optional[int]:
        """חישוב אחוז ההנחה"""
        if self.original_price and self.selling_price:
            discount = (self.original_price - self.selling_price) / self.original_price * 100
            return int(round(discount))
        return None
    
    def is_expiring_soon(self, days: int = 7) -> bool:
        """בדיקה האם הקופון פג בקרוב"""
        if not self.expires_at:
            return False
        
        threshold = datetime.now(timezone.utc) + timedelta(days=days)
        return self.expires_at <= threshold
    
    def can_create_auction(self) -> bool:
        """בדיקה האם ניתן ליצור מכרז לקופון"""
        return (
            self.coupon_type in [CouponType.AUCTION, CouponType.BOTH] and
            self.status == CouponStatus.ACTIVE and
            self.remaining_quantity > 0
        )
    
    def update_price(self, new_price: Decimal) -> Decimal:
        """עדכון מחיר וחישוב הפרש"""
        old_price = self.selling_price
        self.selling_price = new_price
        self.discount_percent = self.calculated_discount_percent
        
        return old_price - new_price  # חיובי = ירידת מחיר
    
    def __repr__(self) -> str:
        return f"<Coupon(id={self.id}, title={self.title[:30]}, price={self.selling_price})>"


class UserFavorite(Base):
    """מועדפים של משתמש"""
    __tablename__ = "user_favorites"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"))
    
    # Notification Preferences
    notify_price_drop: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_similar: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_expiry: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Tracking
    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # מחיר בזמן השמירה
    price_alerts_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_price_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
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
    user: Mapped["User"] = relationship("User")
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="favorites")
    
    # Indexes & Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "coupon_id", name="uq_user_coupon_favorite"),
        Index("idx_favorites_user", "user_id"),
        Index("idx_favorites_coupon", "coupon_id"),
        Index("idx_favorites_notifications", "notify_price_drop", "notify_expiry"),
    )
    
    def should_notify_price_drop(self, current_price: Decimal, threshold_percent: int = 10) -> bool:
        """בדיקה האם לשלוח התראת ירידת מחיר"""
        if not self.notify_price_drop:
            return False
        
        price_drop_percent = (self.original_price - current_price) / self.original_price * 100
        return price_drop_percent >= threshold_percent
    
    def __repr__(self) -> str:
        return f"<UserFavorite(user_id={self.user_id}, coupon_id={self.coupon_id})>"


class CouponRating(Base):
    """דירוג קופון/מוכר"""
    __tablename__ = "coupon_ratings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    
    # Foreign Keys
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    coupon_id: Mapped[str] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"))
    
    # Rating Details
    rating: Mapped[int] = mapped_column(Integer)  # 1-5 כוכבים
    comment: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)  # עד 15 תווים כמו בדרישות
    
    # Metadata
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        init=False
    )
    
    # === Relationships ===
    order: Mapped["Order"] = relationship("Order")
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    coupon: Mapped["Coupon"] = relationship("Coupon")
    
    # Indexes & Constraints
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_rating_per_order"),
        Index("idx_ratings_seller", "seller_id"),
        Index("idx_ratings_coupon", "coupon_id"),
        Index("idx_ratings_buyer", "buyer_id"),
        Index("idx_ratings_rating", "rating"),
        Index("idx_ratings_created", "created_at"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_rating_range"),
        CheckConstraint("char_length(comment) <= 150", name="chk_comment_length"),
    )
    
    def __repr__(self) -> str:
        return f"<CouponRating(order_id={self.order_id}, rating={self.rating})>"


# === Helper Functions ===

def get_trending_coupons(limit: int = 10) -> list[str]:
    """קבלת קופונים טרנדיים (לפי צפיות ומועדפים)"""
    # TODO: SQL Query עבור קופונים פופולריים
    pass


def get_expiring_soon_coupons(days: int = 7) -> list[str]:
    """קבלת קופונים שפגים בקרוב"""
    # TODO: SQL Query עבור קופונים שפגים בקרוב
    pass


def search_coupons(
    query: str,
    category_id: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    city: Optional[str] = None,
    limit: int = 20
) -> list[str]:
    """חיפוש קופונים לפי קריטריונים"""
    # TODO: Full-text search + filters
    pass


def get_similar_coupons(coupon_id: str, limit: int = 5) -> list[str]:
    """קבלת קופונים דומים"""
    # TODO: ML-based similarity או פשוט category + price range
    pass


def update_coupon_stats():
    """עדכון סטטיסטיקות קופונים"""
    # TODO: עדכון view_count, favorite_count, etc.
    pass


def cleanup_expired_coupons():
    """ניקוי קופונים שפגו"""
    # TODO: עדכון status לקופונים שפגו
    pass


# === Category Management ===

def initialize_default_categories():
    """אתחול קטגוריות ברירת מחדל"""
    from app.config import COUPON_CATEGORIES
    
    categories = []
    for category_id, name_he in COUPON_CATEGORIES.items():
        icon = name_he.split()[0]  # החלק הראשון הוא האימוג'י
        name_clean = " ".join(name_he.split()[1:])  # השאר הוא השם
        
        category = CouponCategory(
            id=category_id,
            name_he=name_he,
            name_en=category_id.replace("_", " ").title(),
            icon_emoji=icon,
            sort_order=list(COUPON_CATEGORIES.keys()).index(category_id)
        )
        categories.append(category)
    
    return categories


# TODO: Advanced Features
"""
עתיד - תכונות מתקדמות:
- CouponBundle - חבילות קופונים
- CouponPromotion - מבצעים מיוחדים  
- CouponAnalytics - אנליטיקה מתקדמת
- GeolocationCoupon - קופונים לפי מיקום GPS
- CouponRecommendation - ML recommendations
- CouponSEO - אופטימיזציה למנועי חיפוש
"""
