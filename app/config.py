"""
הגדרות המערכת - Config & Settings
תמיכה בסביבות שונות: development, production
"""

import os
from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """הגדרות המערכת עם תמיכה ב-environment variables"""
    
    # === הגדרות בסיסיות ===
    APP_NAME: str = "Telegram Marketplace Bot"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="Environment: development, production")
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # === Telegram Bot ===
    TELEGRAM_BOT_TOKEN: str = Field(..., description="טוקן הבוט מ-BotFather")
    ADMIN_CHAT_IDS: list[int] = Field(default=[], description="רשימת chat_id של אדמינים")
    LOG_CHANNEL_ID: Optional[int] = Field(default=None, description="ID של ערוץ הלוגים")
    
    # === מסד נתונים ===
    DATABASE_URL: str = Field(..., description="כתובת מסד הנתונים")
    DATABASE_ECHO: bool = Field(default=False, description="הצגת SQL queries בלוגים")
    DATABASE_POOL_SIZE: int = Field(default=10, description="גודל pool החיבורים")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="מקסימום overflow connections")
    
    # === FastAPI Server ===
    HOST: str = Field(default="0.0.0.0", description="Host address")
    PORT: int = Field(default=8000, description="Port number")
    WORKERS: int = Field(default=1, description="מספר workers")
    
    # === אבטחה ===
    SECRET_KEY: str = Field(..., description="מפתח סודי להצפנה")
    JWT_ALGORITHM: str = Field(default="HS256", description="אלגוריתם JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="תוקף טוקן בדקות")
    
    # === עמלות ===
    BUYER_FEE_PERCENT: float = Field(default=2.0, description="עמלת קונה באחוזים")
    SELLER_UNVERIFIED_FEE_PERCENT: float = Field(default=5.0, description="עמלת מוכר לא מאומת")
    SELLER_VERIFIED_FEE_PERCENT: float = Field(default=3.0, description="עמלת מוכר מאומת")
    WITHDRAWAL_FEE_PERCENT: float = Field(default=1.0, description="עמלת משיכה")
    MIN_WITHDRAWAL_AMOUNT: int = Field(default=200, description="סכום משיכה מינימלי בש״ח")
    WITHDRAWAL_HOLD_HOURS: int = Field(default=24, description="זמן החזקה בשעות לפני משיכה")
    
    # === קבצים ו-uploads ===
    UPLOAD_DIR: str = Field(default="uploads", description="תיקייה לקבצים")
    MAX_FILE_SIZE: int = Field(default=5 * 1024 * 1024, description="גודל קובץ מקסימלי (5MB)")
    ALLOWED_FILE_EXTENSIONS: list[str] = Field(
        default=["jpg", "jpeg", "png", "pdf", "gif"], 
        description="סוגי קבצים מותרים"
    )
    
    # === Cache & Redis (אופציונלי לעתיד) ===
    REDIS_URL: Optional[str] = Field(default=None, description="כתובת Redis (אופציונלי)")
    CACHE_TTL: int = Field(default=300, description="זמן cache בשניות")
    
    # === לוגים ===
    LOG_LEVEL: str = Field(default="INFO", description="רמת לוגים")
    LOG_FORMAT: str = Field(default="json", description="פורמט לוגים: json/text")
    
    # === הגדרות מכרזים ===
    MIN_AUCTION_DURATION_HOURS: int = Field(default=1, description="משך מכרז מינימלי")
    MAX_AUCTION_DURATION_HOURS: int = Field(default=168, description="משך מכרז מקסימלי (שבוע)")
    AUCTION_EXTENSION_MINUTES: int = Field(default=10, description="הארכה אוטומטית במכרז")
    
    # === התראות ===
    ENABLE_NOTIFICATIONS: bool = Field(default=True, description="הפעלת התראות")
    PRICE_DROP_THRESHOLD_PERCENT: int = Field(default=10, description="אחוז ירידת מחיר להתראה")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @validator("ADMIN_CHAT_IDS", pre=True)
    def parse_admin_chat_ids(cls, v):
        """המרת רשימת chat_ids ממחרוזת לרשימה"""
        if isinstance(v, str):
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",")]
        return v
    
    @validator("ALLOWED_FILE_EXTENSIONS", pre=True)
    def parse_file_extensions(cls, v):
        """המרת רשימת סיומות קבצים"""
        if isinstance(v, str):
            return [x.strip().lower() for x in v.split(",")]
        return [ext.lower() for ext in v]
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """וידוא סביבה תקינה"""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of: {allowed}")
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """וידוא כתובת מסד נתונים תקינה"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v
    
    @property
    def is_production(self) -> bool:
        """בדיקה האם זו סביבת production"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """בדיקה האם זו סביבת פיתוח"""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def database_url_sync(self) -> str:
        """כתובת מסד נתונים סינכרונית (לאלמביק)"""
        return self.DATABASE_URL.replace("+asyncpg", "")


# יצירת instance יחיד של Settings
settings = Settings()


# === הגדרות קטגוריות קופונים ===
COUPON_CATEGORIES = {
    "food": "🍕 מסעדות ואוכל",
    "fashion": "👗 אופנה וביגוד",
    "beauty": "💄 יופי ובריאות",
    "electronics": "📱 אלקטרוניקה",
    "entertainment": "🎬 בילויים וקולנוע",
    "travel": "✈️ טיסות ונסיעות",
    "sports": "⚽ ספורט וכושר",
    "education": "📚 חינוך ולימודים",
    "services": "🔧 שירותים",
    "other": "🎁 אחר"
}

# === הודעות המערכת (בעברית) ===
MESSAGES = {
    "welcome": "ברוך הבא ל{app_name}! 🎉\nכאן תוכל לקנות ולמכור קופונים וכרטיסים.",
    "choose_role": "אנא בחר את התפקיד שלך:",
    "buyer_menu": "🛒 תפריט קונה",
    "seller_menu": "💼 תפריט מוכר",
    "admin_menu": "⚙️ תפריט אדמין",
    "insufficient_balance": "❌ יתרה לא מספקת. יתרתך הנוכחית: {balance}₪",
    "payment_success": "✅ התשלום בוצע בהצלחה!",
    "invalid_amount": "❌ סכום לא תקין",
    "error_occurred": "❌ אירעה שגיאה: {error}",
    "unauthorized": "❌ אין לך הרשאה לפעולה זו",
    "seller_not_verified": "⚠️ מוכר לא מאומת - עמלה: {fee}%",
    "seller_verified": "✅ מוכר מאומת - עמלה: {fee}%"
}

# === הגדרות לוגים ===
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False
        },
        "telegram": {
            "level": "WARNING"
        },
        "httpx": {
            "level": "WARNING"
        }
    }
}


def get_settings() -> Settings:
    """החזרת instance של Settings - שימושי ל-dependency injection"""
    return settings


# === הגדרות נוספות לפיתוח ===
if settings.is_development:
    # הגדרות debug נוספות
    LOGGING_CONFIG["handlers"]["default"]["level"] = "DEBUG"
    LOGGING_CONFIG["loggers"][""]["level"] = "DEBUG"
