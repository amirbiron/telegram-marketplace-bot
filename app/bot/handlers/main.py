"""
מטפלי הבוט הראשיים - Main Bot Handlers
תפריטים ראשיים, הרשמה, ניהול משתמשים
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal

from telegram import Update, Message
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TelegramError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_manager
from app.models.user import User, UserRole, Wallet, SellerProfile, VerificationStatus
from app.models.coupon import CouponCategory
from app.services.wallet_service import WalletService
from app.bot.keyboards import (
    MainMenuKeyboards, WalletKeyboards, CouponKeyboards,
    KeyboardFactory, get_confirmation_keyboard
)
from app.config import settings, MESSAGES, COUPON_CATEGORIES

logger = logging.getLogger(__name__)

# Conversation States
CHOOSING_ROLE, SELLER_REGISTRATION = range(2)


class MainHandlers:
    """מטפלי הבוט הראשיים"""
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """פקודת /start - נקודת כניסה למערכת"""
        try:
            user_telegram = update.effective_user
            if not user_telegram:
                return ConversationHandler.END
            
            async with db_manager.get_session() as session:
                # בדיקה אם המשתמש כבר קיים
                stmt = select(User).where(User.telegram_user_id == user_telegram.id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                welcome_msg = MESSAGES["welcome"].format(app_name=settings.APP_NAME)
                
                if user:
                    # משתמש קיים - הצגת התפריט המתאים
                    if user.is_blocked:
                        await update.message.reply_text("❌ החשבון שלך חסום. פנה לתמיכה.")
                        return ConversationHandler.END
                    
                    # עדכון פעילות אחרונה
                    user.last_activity_at = user.updated_at
                    await session.commit()
                    
                    # שליחת התפריט המתאים
                    keyboard = KeyboardFactory.get_keyboard_for_user_role(user.role)
                    
                    await update.message.reply_text(
                        f"שלום {user.first_name}! 👋\n{welcome_msg}",
                        reply_markup=keyboard
                    )
                    
                    # שמירת נתוני משתמש בהקשר
                    context.user_data.update({
                        'user_id': user.id,
                        'telegram_user_id': user.telegram_user_id,
                        'role': user.role,
                        'username': user.username,
                        'first_name': user.first_name
                    })
                    
                    return ConversationHandler.END
                
                else:
                    # משתמש חדש - בחירת תפקיד
                    keyboard = MainMenuKeyboards.get_role_selection()
                    
                    await update.message.reply_text(
                        f"{welcome_msg}\n\n{MESSAGES['choose_role']}",
                        reply_markup=keyboard
                    )
                    
                    # שמירת נתוני טלגרם זמנית
                    context.user_data.update({
                        'telegram_user_id': user_telegram.id,
                        'username': user_telegram.username,
                        'first_name': user_telegram.first_name or "משתמש",
                        'last_name': user_telegram.last_name
                    })
                    
                    return CHOOSING_ROLE
        
        except Exception as e:
            logger.error(f"Start command failed: {e}")
            await update.message.reply_text(MESSAGES["error_occurred"].format(error="שגיאה בהתחברות"))
            return ConversationHandler.END
    
    @staticmethod
    async def role_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """בחירת תפקיד משתמש חדש"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "role_buyer":
            return await MainHandlers._create_buyer_user(query, context)
        elif query.data == "role_seller":
            # מוכר צריך רישום נוסף
            keyboard = get_confirmation_keyboard(
                "confirm_seller_registration",
                "back_to_role_selection",
                "✅ המשך להרשמה",
                "🔙 חזרה"
            )
            
            await query.edit_message_text(
                "📋 הרשמה כמוכר\n\n"
                "כמוכר תוכל:\n"
                "• להעלות קופונים למכירה\n"
                "• ליצור מכרזים\n"
                "• לקבל תשלומים\n"
                "• לעבור תהליך אימות (מומלץ)\n\n"
                "האם תרצה להמשיך?",
                reply_markup=keyboard
            )
            return SELLER_REGISTRATION
        
        elif query.data == "info_system":
            return await MainHandlers._show_system_info(query, context)
    
    @staticmethod
    async def _create_buyer_user(query, context: ContextTypes.DEFAULT_TYPE) -> int:
        """יצירת משתמש קונה"""
        try:
            async with db_manager.get_session() as session:
                # יצירת משתמש חדש
                new_user = User(
                    telegram_user_id=context.user_data['telegram_user_id'],
                    username=context.user_data.get('username'),
                    first_name=context.user_data['first_name'],
                    last_name=context.user_data.get('last_name'),
                    role=UserRole.BUYER
                )
                
                session.add(new_user)
                await session.flush()
                
                # יצירת ארנק
                wallet_service = WalletService(session)
                wallet = await wallet_service.create_wallet(new_user.id)
                
                await session.commit()
                
                # עדכון הקשר
                context.user_data.update({
                    'user_id': new_user.id,
                    'role': UserRole.BUYER
                })
                
                # שליחת תפריט קונה
                keyboard = MainMenuKeyboards.get_buyer_menu()
                
                await query.edit_message_text(
                    f"✅ נרשמת בהצלחה כקונה!\n\n"
                    f"שלום {new_user.first_name}! 🛒\n"
                    f"זה התפריט שלך:",
                    reply_markup=keyboard
                )
                
                return ConversationHandler.END
        
        except Exception as e:
            logger.exception("Failed to create buyer", exc_info=True)
            await query.edit_message_text(
                "❌ שגיאה ביצירת המשתמש. נסה שוב מאוחר יותר."
            )
            return ConversationHandler.END
    
    @staticmethod
    async def seller_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """אישור הרשמת מוכר"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_seller_registration":
            return await MainHandlers._create_seller_user(query, context)
        elif query.data == "back_to_role_selection":
            keyboard = MainMenuKeyboards.get_role_selection()
            await query.edit_message_text(
                MESSAGES["choose_role"],
                reply_markup=keyboard
            )
            return CHOOSING_ROLE
    
    @staticmethod
    async def _create_seller_user(query, context: ContextTypes.DEFAULT_TYPE) -> int:
        """יצירת משתמש מוכר"""
        try:
            async with db_manager.get_session() as session:
                # יצירת משתמש חדש
                new_user = User(
                    telegram_user_id=context.user_data['telegram_user_id'],
                    username=context.user_data.get('username'),
                    first_name=context.user_data['first_name'],
                    last_name=context.user_data.get('last_name'),
                    role=UserRole.SELLER
                )
                
                session.add(new_user)
                await session.flush()
                
                # יצירת פרופיל מוכר (אחרי שה-user נשמר וקיבל id)
                seller_profile = SellerProfile(
                    user_id=new_user.id,
                    business_name="",
                    description="",
                    verification_documents=[],
                    verified_at=None,
                    verified_by_admin_id=None,
                    average_rating=Decimal('0.00'),
                    is_verified=False,
                    verification_status=VerificationStatus.UNVERIFIED,
                    daily_quota=10,
                    daily_count=0,
                    total_sales=0,
                    total_ratings=0
                )
                
                session.add(seller_profile)
                await session.flush()
                
                # יצירת ארנק (אחרי שה-user נשמר)
                wallet_service = WalletService(session)
                wallet = await wallet_service.create_wallet(user_id=new_user.id)
                
                await session.commit()
                
                # עדכון הקשר
                context.user_data.update({
                    'user_id': new_user.id,
                    'role': UserRole.SELLER
                })
                
                # שליחת תפריט מוכר
                keyboard = MainMenuKeyboards.get_seller_menu(
                    is_verified=False,
                    daily_quota_used=0,
                    daily_quota_max=10
                )
                
                await query.edit_message_text(
                    f"✅ נרשמת בהצלחה כמוכר!\n\n"
                    f"שלום {new_user.first_name}! 💼\n\n"
                    f"📋 מידע חשוב:\n"
                    f"• מכסה יומית: 10 קופונים (ללא אימות)\n"
                    f"• עמלת מכירה: {settings.SELLER_UNVERIFIED_FEE_PERCENT}% (ללא אימות)\n"
                    f"• מומלץ לעבור אימות לתנאים טובים יותר\n\n"
                    f"זה התפריט שלך:",
                    reply_markup=keyboard
                )
                
                # הודעה לאדמינים על מוכר חדש
                if settings.LOG_CHANNEL_ID:
                    try:
                        await context.bot.send_message(
                            chat_id=settings.LOG_CHANNEL_ID,
                            text=f"🆕 מוכר חדש נרשם:\n"
                                 f"שם: {new_user.first_name}\n"
                                 f"משתמש: @{new_user.username or 'לא זמין'}\n"
                                 f"ID: {new_user.id}"
                        )
                    except TelegramError:
                        pass
                
                return ConversationHandler.END
        
        except Exception as e:
            logger.exception("Failed to create seller", exc_info=True)
            await query.edit_message_text(
                "❌ שגיאה ביצירת המשתמש. נסה שוב מאוחר יותר."
            )
            return ConversationHandler.END
    
    @staticmethod
    async def _show_system_info(query, context: ContextTypes.DEFAULT_TYPE) -> int:
        """הצגת מידע על המערכת"""
        info_text = (
            f"📋 מידע על {settings.APP_NAME}\n\n"
            f"🎯 מטרה: מרקטפלייס לקופונים וכרטיסים\n\n"
            f"👥 סוגי משתמשים:\n"
            f"🛒 קונה - רכישת קופונים ומכרזים\n"
            f"💼 מוכר - מכירת קופונים ויצירת מכרזים\n\n"
            f"💰 עמלות:\n"
            f"• קונה: {settings.BUYER_FEE_PERCENT}%\n"
            f"• מוכר מאומת: {settings.SELLER_VERIFIED_FEE_PERCENT}%\n"
            f"• מוכר לא מאומת: {settings.SELLER_UNVERIFIED_FEE_PERCENT}%\n\n"
            f"🛡️ בטיחות:\n"
            f"• מערכת דירוגים ומחלוקות\n"
            f"• חלון דיווח 12 שעות\n"
            f"• שחרור תשלום אחרי 24 שעות\n\n"
            f"גרסה: {settings.VERSION}"
        )
        
        keyboard = MainMenuKeyboards.get_role_selection()
        
        await query.edit_message_text(
            info_text,
            reply_markup=keyboard
        )
        
        return CHOOSING_ROLE


class MenuHandlers:
    """מטפלי תפריטים"""
    
    @staticmethod
    async def buyer_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """תפריט קונה"""
        query = update.callback_query
        await query.answer()
        
        user_data = context.user_data
        keyboard = MainMenuKeyboards.get_buyer_menu()
        
        await query.edit_message_text(
            f"🛒 תפריט קונה\n\nשלום {user_data.get('first_name', 'משתמש')}!",
            reply_markup=keyboard
        )
    
    @staticmethod
    async def seller_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """תפריט מוכר"""
        query = update.callback_query
        await query.answer()
        
        try:
            async with db_manager.get_session() as session:
                user_id = context.user_data.get('user_id')
                
                # קבלת פרטי מוכר
                stmt = select(SellerProfile).where(SellerProfile.user_id == user_id)
                result = await session.execute(stmt)
                seller_profile = result.scalar_one_or_none()
                
                if seller_profile:
                    keyboard = MainMenuKeyboards.get_seller_menu(
                        is_verified=seller_profile.is_verified,
                        daily_quota_used=seller_profile.daily_count,
                        daily_quota_max=seller_profile.daily_quota
                    )
                    
                    verification_status = "✅ מאומת" if seller_profile.is_verified else "⚠️ לא מאומת"
                    
                    await query.edit_message_text(
                        f"💼 תפריט מוכר\n\n"
                        f"שלום {context.user_data.get('first_name')}!\n"
                        f"סטטוס: {verification_status}\n"
                        f"מכסה יומית: {seller_profile.daily_count}/{seller_profile.daily_quota}",
                        reply_markup=keyboard
                    )
                else:
                    await query.edit_message_text("❌ שגיאה בטעינת פרטי מוכר")
        
        except Exception as e:
            logger.error(f"Seller menu error: {e}")
            await query.edit_message_text("❌ שגיאה בטעינת התפריט")
    
    @staticmethod
    async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """תפריט אדמין"""
        query = update.callback_query
        await query.answer()
        
        # בדיקת הרשאות אדמין
        user_role = context.user_data.get('role')
        if user_role != UserRole.ADMIN:
            await query.answer("❌ אין לך הרשאות אדמין", show_alert=True)
            return
        
        keyboard = MainMenuKeyboards.get_admin_menu()
        
        await query.edit_message_text(
            f"⚙️ תפריט אדמין\n\nשלום {context.user_data.get('first_name')}!",
            reply_markup=keyboard
        )


class WalletHandlers:
    """מטפלי ארנק ויתרות"""
    
    @staticmethod
    async def wallet_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """תפריט ארנק"""
        query = update.callback_query
        await query.answer()
        
        try:
            async with db_manager.get_session() as session:
                user_id = context.user_data.get('user_id')
                wallet_service = WalletService(session)
                
                # קבלת יתרות
                balance_display = await wallet_service.get_balance_display(user_id)
                
                keyboard = WalletKeyboards.get_wallet_menu(balance_display)
                
                balance_text = (
                    f"💰 הארנק שלי\n\n"
                    f"💰 יתרה כוללת: {balance_display['total']}₪\n"
                    f"🔒 יתרה קפואה: {balance_display['locked']}₪\n"
                    f"✅ יתרה זמינה: {balance_display['available']}₪"
                )
                
                await query.edit_message_text(
                    balance_text,
                    reply_markup=keyboard
                )
        
        except Exception as e:
            logger.error(f"Wallet menu error: {e}")
            await query.edit_message_text("❌ שגיאה בטעינת הארנק")
    
    @staticmethod
    async def add_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """הוספת יתרה"""
        query = update.callback_query
        await query.answer()
        
        keyboard = WalletKeyboards.get_add_balance_amounts()
        
        await query.edit_message_text(
            "💳 הוסף יתרה\n\nבחר סכום:",
            reply_markup=keyboard
        )
    
    @staticmethod
    async def refresh_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """רענון יתרה"""
        query = update.callback_query
        await query.answer("🔄 מרענן יתרה...")
        
        # קריאה שוב לתפריט ארנק
        await WalletHandlers.wallet_menu_callback(update, context)


class CouponHandlers:
    """מטפלי קופונים"""
    
    @staticmethod
    async def browse_coupons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """דפדוף קופונים"""
        query = update.callback_query
        await query.answer()
        
        keyboard = CouponKeyboards.get_categories()
        
        await query.edit_message_text(
            "🛍️ דפדף קופונים\n\nבחר קטגוריה:",
            reply_markup=keyboard
        )
    
    @staticmethod
    async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """בחירת קטגוריה"""
        query = update.callback_query
        await query.answer()
        
        # חילוץ קטגוריה מהנתונים
        category_id = query.data.replace("category_", "")
        category_name = COUPON_CATEGORIES.get(category_id, "קטגוריה לא ידועה")
        
        # TODO: הצגת קופונים בקטגוריה
        await query.edit_message_text(
            f"📂 {category_name}\n\nטוען קופונים..."
        )
        
        # כאן יבוא לוגיקה לטעינת קופונים מהמסד נתונים
        # ועיצוב עם pagination וכו'


class SystemHandlers:
    """מטפלי מערכת כלליים"""
    
    @staticmethod
    async def contact_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """פנייה למערכת"""
        query = update.callback_query
        await query.answer()
        
        from app.bot.keyboards import NotificationKeyboards
        keyboard = NotificationKeyboards.get_contact_support_options()
        
        await query.edit_message_text(
            "📩 פנייה למערכת\n\nאיך נוכל לעזור לך?",
            reply_markup=keyboard
        )
    
    @staticmethod
    async def terms_policy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """תקנון ומדיניות"""
        query = update.callback_query
        await query.answer()
        
        terms_text = (
            "📋 תקנון ומדיניות\n\n"
            "1️⃣ כללי שימוש\n"
            "• השימוש במערכת מותנה בקבלת התקנון\n"
            "• אסור להעלות תוכן פוגעני או לא חוקי\n\n"
            "2️⃣ עמלות\n"
            f"• קונה: {settings.BUYER_FEE_PERCENT}%\n"
            f"• מוכר מאומת: {settings.SELLER_VERIFIED_FEE_PERCENT}%\n"
            f"• מוכר לא מאומת: {settings.SELLER_UNVERIFIED_FEE_PERCENT}%\n"
            f"• משיכה: {settings.WITHDRAWAL_FEE_PERCENT}%\n\n"
            "3️⃣ מחלוקות\n"
            "• חלון דיווח: 12 שעות\n"
            "• שחרור תשלום: 24 שעות\n"
            "• הכרעת אדמין היא סופית\n\n"
            "4️⃣ אחריות\n"
            "• המערכת משמשת כפלטפורמה בלבד\n"
            "• אחריות לקופונים על המוכר\n\n"
            "לפרטים נוספים: /contact"
        )
        
        keyboard = MainMenuKeyboards.get_back_to_main(context.user_data.get('role', UserRole.BUYER))
        
        await query.edit_message_text(
            terms_text,
            reply_markup=keyboard
        )
    
    @staticmethod
    async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """callback לא מוכר"""
        query = update.callback_query
        await query.answer("❌ פעולה לא זמינה כרגע", show_alert=True)
    
    @staticmethod
    async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ביטול פעולה"""
        query = update.callback_query
        if query:
            await query.answer()
            
            user_role = context.user_data.get('role', UserRole.BUYER)
            keyboard = KeyboardFactory.get_keyboard_for_user_role(user_role)
            
            await query.edit_message_text(
                "❌ הפעולה בוטלה",
                reply_markup=keyboard
            )
        
        return ConversationHandler.END


# === Helper Functions ===

async def get_user_from_context(context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> Optional[User]:
    """קבלת משתמש מההקשר"""
    user_id = context.user_data.get('user_id')
    if not user_id:
        return None
    
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_activity(user_id: int, session: AsyncSession) -> None:
    """עדכון פעילות משתמש אחרונה"""
    try:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.last_activity_at = user.updated_at
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to update user activity: {e}")


def require_user_role(required_role: UserRole):
    """דקורטור לבדיקת הרשאות משתמש"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_role = context.user_data.get('role')
            if user_role != required_role:
                query = update.callback_query
                if query:
                    await query.answer("❌ אין לך הרשאה לפעולה זו", show_alert=True)
                return
            
            return await func(update, context)
        return wrapper
    return decorator


# === Error Handlers ===

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בשגיאות כלליות"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ אירעה שגיאה. נסה שוב מאוחר יותר."
            )
    except Exception:
        pass


# === Conversation Handler ===

def get_main_conversation_handler() -> ConversationHandler:
    """יצירת conversation handler ראשי"""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('start', MainHandlers.start_command)
        ],
        states={
            CHOOSING_ROLE: [
                CallbackQueryHandler(
                    MainHandlers.role_selection_callback,
                    pattern='^(role_buyer|role_seller|info_system)$'
                )
            ],
            SELLER_REGISTRATION: [
                CallbackQueryHandler(
                    MainHandlers.seller_registration_callback,
                    pattern='^(confirm_seller_registration|back_to_role_selection)$'
                )
            ],
        },
        fallbacks=[
            CallbackQueryHandler(SystemHandlers.cancel_action, pattern='^cancel$'),
            CommandHandler('cancel', SystemHandlers.cancel_action)
        ],
        allow_reentry=True,
        per_message=False
    )


# TODO: Advanced Handler Features
"""
עתיד - תכונות מתקדמות:
- Smart context management
- User behavior analytics
- A/B testing for UI flows
- Personalized recommendations
- Voice message support
- Multi-language support
- Accessibility features
- Smart notifications based on user activity
"""
