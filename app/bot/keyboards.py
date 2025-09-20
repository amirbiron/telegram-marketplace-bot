"""
מקלדות בוט טלגרם - Telegram Keyboards
UI/UX מתקדם עם תמיכה בכל התכונות החדשות
רק כפתורי inline - בלי reply keyboards
"""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from datetime import datetime, timezone

from telegram import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)

from app.config import COUPON_CATEGORIES, MESSAGES
from app.models.user import UserRole
from app.models.order import OrderStatus, DisputeReason
from app.models.coupon import CouponStatus


class KeyboardBuilder:
    """בנאי מקלדות מתקדם"""
    
    @staticmethod
    def build_inline_keyboard(
        buttons: List[List[Tuple[str, str]]], 
        row_width: int = 2
    ) -> InlineKeyboardMarkup:
        """בניית מקלדת inline מתקדמת"""
        keyboard = []
        
        for row in buttons:
            button_row = []
            for text, callback_data in row:
                button_row.append(InlineKeyboardButton(text, callback_data=callback_data))
            keyboard.append(button_row)
        
        return InlineKeyboardMarkup(keyboard)


class MainMenuKeyboards:
    """מקלדות תפריט ראשי"""
    
    @staticmethod
    def get_role_selection() -> InlineKeyboardMarkup:
        """בחירת תפקיד ראשונית"""
        buttons = [
            [("🛒 קונה", "role_buyer")],
            [("💼 מוכר", "role_seller")],
            [("📋 מידע על המערכת", "info_system")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_buyer_menu() -> InlineKeyboardMarkup:
        """תפריט קונה עיקרי"""
        buttons = [
            [("🛍️ דפדף קופונים", "browse_coupons"), ("🎯 מכרזים פעילים", "view_auctions")],
            [("⭐ המועדפים שלי", "my_favorites"), ("🛒 הקניות שלי", "my_purchases")],
            [("💰 ארנק", "wallet_menu"), ("📊 היסטוריה", "transaction_history")],
            [("💬 הצ'אטים שלי", "my_chats"), ("📩 פנה למערכת", "contact_support")],
            [("⚙️ הגדרות", "settings"), ("📋 תקנון ומדיניות", "terms_policy")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_seller_menu(is_verified: bool = False, daily_quota_used: int = 0, daily_quota_max: int = 10) -> InlineKeyboardMarkup:
        """תפריט מוכר עיקרי"""
        # אייקון מאומת
        verification_icon = "✅" if is_verified else "⚠️"
        quota_text = f"📤 העלה קופון ({daily_quota_used}/{daily_quota_max})"
        
        buttons = [
            [(f"{quota_text}", "upload_coupon"), ("📋 הקופונים שלי", "my_coupons")],
            [("💰 ארנק", "wallet_menu"), ("📊 מכירות", "sales_history")],
            [("🎯 צור מכרז", "create_auction"), ("📈 נתונים סטטיסטיים", "seller_analytics")],
            [("💬 הצ'אטים שלי", "my_chats"), (f"{verification_icon} אימות מוכר", "seller_verification")],
            [("⚙️ הגדרות", "settings"), ("📩 פנה למערכת", "contact_support")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_admin_menu() -> InlineKeyboardMarkup:
        """תפריט אדמין עיקרי"""
        buttons = [
            [("👥 ניהול משתמשים", "admin_users"), ("🏪 ניהול מוכרים", "admin_sellers")],
            [("🛍️ ניהול קופונים", "admin_coupons"), ("🎯 ניהול מכרזים", "admin_auctions")],
            [("🚨 מחלוקות פתוחות", "admin_disputes"), ("💰 ניהול יתרות", "admin_wallets")],
            [("📊 דוחות ונתונים", "admin_reports"), ("⚙️ הגדרות מערכת", "admin_settings")],
            [("🔔 התראות", "admin_notifications"), ("📋 לוגים", "admin_logs")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_back_to_main(user_role: UserRole) -> InlineKeyboardMarkup:
        """חזרה לתפריט ראשי לפי תפקיד"""
        role_map = {
            UserRole.BUYER: ("🛒 חזרה לתפריט קונה", "buyer_menu"),
            UserRole.SELLER: ("💼 חזרה לתפריט מוכר", "seller_menu"),
            UserRole.ADMIN: ("⚙️ חזרה לתפריט אדמין", "admin_menu")
        }
        
        text, callback = role_map.get(user_role, ("🏠 תפריט ראשי", "main_menu"))
        buttons = [[(text, callback)]]
        return KeyboardBuilder.build_inline_keyboard(buttons)


class WalletKeyboards:
    """מקלדות ארנק ויתרות"""
    
    @staticmethod
    def get_wallet_menu(balance: Dict[str, Decimal]) -> InlineKeyboardMarkup:
        """תפריט ארנק עם הצגת יתרות"""
        buttons = [
            [("💳 הוסף יתרה", "add_balance"), ("💸 בקש משיכה", "request_withdrawal")],
            [("📊 היסטוריית תנועות", "transaction_history"), ("🔒 נעילות פעילות", "active_locks")],
            [("📋 פרטי ארנק", "wallet_details"), ("🔄 רענן יתרה", "refresh_balance")],
            [("🏠 חזרה", "back_to_main")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_add_balance_amounts() -> InlineKeyboardMarkup:
        """בחירת סכומי הוספת יתרה"""
        amounts = [50, 100, 200, 500, 1000]
        buttons = []
        
        # שתי עמודות
        for i in range(0, len(amounts), 2):
            row = []
            for j in range(2):
                if i + j < len(amounts):
                    amount = amounts[i + j]
                    row.append((f"{amount}₪", f"add_amount_{amount}"))
            buttons.append(row)
        
        buttons.append([("💰 סכום אחר", "add_custom_amount")])
        buttons.append([("🔙 חזרה", "wallet_menu")])
        return KeyboardBuilder.build_inline_keyboard(buttons)


class CouponKeyboards:
    """מקלדות קופונים וקטגוריות"""
    
    @staticmethod
    def get_categories() -> InlineKeyboardMarkup:
        """בחירת קטגוריות - כל הכפתורים inline"""
        buttons = []
        categories = list(COUPON_CATEGORIES.items())
        
        # שתי קטגוריות בשורה
        for i in range(0, len(categories), 2):
            row = []
            for j in range(2):
                if i + j < len(categories):
                    cat_id, cat_name = categories[i + j]
                    row.append((cat_name, f"category_{cat_id}"))
            buttons.append(row)
        
        buttons.append([("🔍 חיפוש מתקדם", "advanced_search")])
        buttons.append([("🏠 חזרה", "back_to_main")])
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_coupon_actions(
        coupon_id: str, 
        is_owner: bool = False, 
        is_favorite: bool = False,
        is_available: bool = True,
        can_auction: bool = False,
        current_price: Optional[Decimal] = None
    ) -> InlineKeyboardMarkup:
        """פעולות על קופון"""
        buttons = []
        
        if is_owner:
            # כפתורי בעלים
            buttons.append([("✏️ עריכה", f"edit_coupon_{coupon_id}"), ("📊 סטטיסטיקות", f"coupon_stats_{coupon_id}")])
            if can_auction:
                buttons.append([("🎯 צור מכרז", f"create_auction_{coupon_id}")])
            buttons.append([("❌ מחק", f"delete_coupon_{coupon_id}")])
        else:
            # כפתורי קונה
            if is_available:
                buy_text = f"💳 קנה" + (f" ({current_price}₪)" if current_price else "")
                buttons.append([(buy_text, f"buy_coupon_{coupon_id}")])
            
            if can_auction:
                buttons.append([("🎯 צפה במכרז", f"view_auction_{coupon_id}")])
            
            # מועדפים
            fav_text = "💔 הסר מהמועדפים" if is_favorite else "⭐ הוסף למועדפים"
            fav_action = "remove_favorite" if is_favorite else "add_favorite"
            buttons.append([(fav_text, f"{fav_action}_{coupon_id}")])
            
            buttons.append([("💬 צ'אט עם המוכר", f"chat_seller_{coupon_id}"), ("📋 דירוגי המוכר", f"seller_ratings_{coupon_id}")])
        
        buttons.append([("📤 שתף", f"share_coupon_{coupon_id}"), ("🔙 חזרה", "browse_coupons")])
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_coupon_filters() -> InlineKeyboardMarkup:
        """מסנני חיפוש"""
        buttons = [
            [("💰 לפי מחיר", "filter_price"), ("📍 לפי מיקום", "filter_location")],
            [("⭐ מדורג גבוה", "filter_rating"), ("🔥 פופולריים", "filter_popular")],
            [("🆕 חדשים", "filter_new"), ("⏰ פגים בקרוב", "filter_expiring")],
            [("🗂️ כל הקטגוריות", "all_categories"), ("🔄 נקה מסננים", "clear_filters")],
            [("🔙 חזרה", "browse_coupons")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)


class OrderKeyboards:
    """מקלדות הזמנות ורכישות - עם תמיכה בטיימרים החדשים"""
    
    @staticmethod
    def get_purchase_confirmation(
        coupon_title: str,
        total_amount: Decimal,
        buyer_fee: Decimal,
        available_balance: Decimal
    ) -> InlineKeyboardMarkup:
        """אישור רכישה"""
        sufficient_balance = available_balance >= (total_amount + buyer_fee)
        
        buttons = []
        
        if sufficient_balance:
            buttons.append([("✅ אשר רכישה", "confirm_purchase")])
        else:
            buttons.append([("💳 הוסף יתרה", "add_balance_purchase")])
        
        buttons.extend([
            [("📋 פרטי עמלות", "fee_breakdown"), ("💰 צפה ביתרה", "view_balance")],
            [("❌ בטל", "cancel_purchase"), ("🔙 חזרה לקופון", "back_to_coupon")]
        ])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_order_actions(
        order_id: str,
        status: OrderStatus,
        is_buyer: bool = True,
        dispute_window_open: bool = False,
        can_confirm: bool = False,
        time_until_dispute_close: Optional[str] = None,
        time_until_auto_release: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """פעולות על הזמנה - תמיכה בכל הטיימרים החדשים"""
        buttons = []
        
        if is_buyer:
            if status == OrderStatus.DELIVERED:
                if can_confirm:
                    buttons.append([("✅ אשר קנייה", f"confirm_order_{order_id}")])
                
                if dispute_window_open:
                    dispute_text = "🚨 דווח על בעיה"
                    if time_until_dispute_close:
                        dispute_text += f" ({time_until_dispute_close})"
                    buttons.append([(dispute_text, f"report_dispute_{order_id}")])
                else:
                    buttons.append([("ℹ️ חלון דיווח נסגר", "dispute_window_closed")])
            
            elif status == OrderStatus.IN_DISPUTE:
                buttons.append([("💬 צ'אט מחלוקת", f"dispute_chat_{order_id}")])
            
            elif status == OrderStatus.RELEASED:
                buttons.append([("✅ הזמנה הושלמה", "order_completed")])
            
            # תמיד זמין לקונה
            buttons.append([("📱 הצג קופון", f"show_coupon_{order_id}"), ("⭐ דרג מוכר", f"rate_seller_{order_id}")])
        
        else:  # מוכר
            if status == OrderStatus.PAID:
                buttons.append([("📤 שלח קופון", f"deliver_coupon_{order_id}")])
            
            elif status == OrderStatus.DELIVERED:
                release_text = "⏰ ממתין לשחרור"
                if time_until_auto_release:
                    release_text += f" ({time_until_auto_release})"
                buttons.append([(release_text, "waiting_for_release")])
            
            elif status == OrderStatus.IN_DISPUTE:
                buttons.append([("💬 צ'אט מחלוקת", f"dispute_chat_{order_id}")])
            
            elif status == OrderStatus.RELEASED:
                buttons.append([("💰 תשלום שוחרר", "payment_released_info")])
        
        buttons.extend([
            [("📊 פרטי הזמנה", f"order_details_{order_id}")],
            [("🔙 חזרה", "my_purchases" if is_buyer else "sales_history")]
        ])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_dispute_reasons() -> InlineKeyboardMarkup:
        """סיבות למחלוקת"""
        reasons = [
            ("קופון לא תקין", DisputeReason.COUPON_INVALID),
            ("קופון פג תוקף", DisputeReason.COUPON_EXPIRED),
            ("קופון כבר נוצל", DisputeReason.COUPON_USED),
            ("פרטים שגויים", DisputeReason.WRONG_DETAILS),
            ("מוכר לא מגיב", DisputeReason.SELLER_UNRESPONSIVE),
            ("אחר", DisputeReason.OTHER)
        ]
        
        buttons = []
        for text, reason in reasons:
            buttons.append([(text, f"dispute_reason_{reason.value}")])
        
        buttons.append([("❌ בטל", "cancel_dispute")])
        return KeyboardBuilder.build_inline_keyboard(buttons)


class AuctionKeyboards:
    """מקלדות מכרזים"""
    
    @staticmethod
    def get_auction_actions(
        auction_id: str,
        current_price: Decimal,
        is_owner: bool = False,
        is_active: bool = True,
        user_bid: Optional[Decimal] = None,
        is_winning: bool = False,
        time_left: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """פעולות על מכרז"""
        buttons = []
        
        if is_owner:
            if is_active:
                buttons.append([("⏹️ עצור מכרז", f"stop_auction_{auction_id}")])
            buttons.append([("📊 סטטיסטיקות", f"auction_stats_{auction_id}")])
        
        else:  # משתתף פוטנציאלי
            if is_active:
                bid_text = "🎯 הצע מחיר"
                if user_bid:
                    status_emoji = "🥇" if is_winning else "❌"
                    bid_text = f"{status_emoji} עדכן הצעה (נוכחי: {user_bid}₪)"
                
                buttons.append([(bid_text, f"bid_auction_{auction_id}")])
                buttons.append([("👥 צפה בהצעות", f"view_bids_{auction_id}")])
            
            else:
                buttons.append([("🏁 מכרז הסתיים", "auction_ended")])
        
        # זמן נותר
        if time_left and is_active:
            buttons.append([("⏰ זמן נותר: " + time_left, "time_remaining")])
        
        buttons.extend([
            [("🔔 התראות", f"auction_alerts_{auction_id}"), ("📤 שתף מכרז", f"share_auction_{auction_id}")],
            [("🔙 חזרה למכרזים", "view_auctions")]
        ])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_bid_amounts(current_price: Decimal, min_increment: Decimal = Decimal("10")) -> InlineKeyboardMarkup:
        """סכומי הצעה מוצעים"""
        buttons = []
        
        # הצעות מוצעות
        suggested_bids = [
            current_price + min_increment,
            current_price + (min_increment * 2),
            current_price + (min_increment * 5),
            current_price + (min_increment * 10)
        ]
        
        for i in range(0, len(suggested_bids), 2):
            row = []
            for j in range(2):
                if i + j < len(suggested_bids):
                    amount = suggested_bids[i + j]
                    row.append((f"{amount}₪", f"bid_amount_{amount}"))
            buttons.append(row)
        
        buttons.extend([
            [("💰 סכום אחר", "custom_bid_amount")],
            [("❌ בטל", "cancel_bid")]
        ])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)


class AdminKeyboards:
    """מקלדות אדמין"""
    
    @staticmethod
    def get_dispute_resolution(order_id: str) -> InlineKeyboardMarkup:
        """פתרון מחלוקת"""
        buttons = [
            [("✅ תמך בקונה - החזר מלא", f"resolve_buyer_full_{order_id}")],
            [("💰 תמך בקונה - החזר חלקי", f"resolve_buyer_partial_{order_id}")],
            [("🛡️ תמך במוכר - שחרר תשלום", f"resolve_seller_{order_id}")],
            [("⚖️ פשרה", f"resolve_compromise_{order_id}")],
            [("📋 צפה בצ'אט מחלוקת", f"view_dispute_chat_{order_id}")],
            [("🔙 חזרה למחלוקות", "admin_disputes")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_seller_verification_actions(seller_id: int) -> InlineKeyboardMarkup:
        """פעולות אימות מוכר"""
        buttons = [
            [("✅ אשר מוכר", f"approve_seller_{seller_id}"), ("❌ דחה בקשה", f"reject_seller_{seller_id}")],
            [("📋 צפה במסמכים", f"view_docs_{seller_id}"), ("💬 צ'אט עם מוכר", f"chat_seller_{seller_id}")],
            [("⚙️ הגדר מכסה יומית", f"set_quota_{seller_id}"), ("🚫 חסום מוכר", f"block_seller_{seller_id}")],
            [("🔙 חזרה", "admin_sellers")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_user_management(user_id: int) -> InlineKeyboardMarkup:
        """ניהול משתמש"""
        buttons = [
            [("💰 הוסף יתרה", f"admin_add_balance_{user_id}"), ("📊 צפה בנתונים", f"user_stats_{user_id}")],
            [("🔒 חסום משתמש", f"block_user_{user_id}"), ("🔓 בטל חסימה", f"unblock_user_{user_id}")],
            [("📋 היסטוריית פעילות", f"user_activity_{user_id}"), ("💬 שלח הודעה", f"message_user_{user_id}")],
            [("🔙 חזרה", "admin_users")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)


class NavigationKeyboards:
    """מקלדות ניווט ופאגינציה"""
    
    @staticmethod
    def get_pagination(
        current_page: int,
        total_pages: int,
        callback_prefix: str,
        extra_data: str = ""
    ) -> InlineKeyboardMarkup:
        """פאגינציה עם ניווט חכם"""
        buttons = []
        
        # כפתורי ניווט
        nav_row = []
        
        if current_page > 1:
            nav_row.append(("⏪ ראשון", f"{callback_prefix}_page_1{extra_data}"))
            nav_row.append(("◀️ הקודם", f"{callback_prefix}_page_{current_page-1}{extra_data}"))
        
        nav_row.append((f"📄 {current_page}/{total_pages}", f"page_info"))
        
        if current_page < total_pages:
            nav_row.append(("▶️ הבא", f"{callback_prefix}_page_{current_page+1}{extra_data}"))
            nav_row.append(("⏩ אחרון", f"{callback_prefix}_page_{total_pages}{extra_data}"))
        
        buttons.append(nav_row)
        
        # קפיצה למספר עמוד
        if total_pages > 5:
            buttons.append([("🔢 קפוץ לעמוד", f"{callback_prefix}_jump_page{extra_data}")])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_list_actions(
        item_type: str,
        has_filters: bool = False,
        can_sort: bool = False,
        can_export: bool = False
    ) -> InlineKeyboardMarkup:
        """פעולות על רשימות"""
        buttons = []
        
        if has_filters:
            buttons.append([("🔍 מסנן", f"filter_{item_type}"), ("🗂️ קטגוריות", f"categories_{item_type}")])
        
        if can_sort:
            buttons.append([("📊 מיון", f"sort_{item_type}"), ("🔄 רענן", f"refresh_{item_type}")])
        
        if can_export:
            buttons.append([("📤 ייצוא", f"export_{item_type}")])
        
        buttons.append([("🏠 תפריט ראשי", "main_menu")])
        
        return KeyboardBuilder.build_inline_keyboard(buttons)


class NotificationKeyboards:
    """מקלדות התראות והגדרות"""
    
    @staticmethod
    def get_notification_settings() -> InlineKeyboardMarkup:
        """הגדרות התראות"""
        buttons = [
            [("💰 התראות מחיר", "toggle_price_notifications"), ("⏰ התראות פקיעה", "toggle_expiry_notifications")],
            [("🎯 התראות מכרזים", "toggle_auction_notifications"), ("📱 התראות כלליות", "toggle_general_notifications")],
            [("🔇 השתק הכל", "mute_all_notifications"), ("🔊 הפעל הכל", "unmute_all_notifications")],
            [("⚙️ הגדרות מתקדמות", "advanced_notification_settings")],
            [("🔙 חזרה להגדרות", "settings")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)
    
    @staticmethod
    def get_contact_support_options() -> InlineKeyboardMarkup:
        """אפשרויות פנייה למערכת"""
        buttons = [
            [("🐛 דיווח על באג", "report_bug"), ("💡 הצעה לשיפור", "feature_request")],
            [("❓ שאלה כללית", "general_question"), ("💰 בעיה בתשלום", "payment_issue")],
            [("🤝 תמיכה טכנית", "technical_support"), ("📋 אחר", "other_support")],
            [("📞 פרטי יצירת קשר", "contact_details"), ("🔙 חזרה", "back_to_main")]
        ]
        return KeyboardBuilder.build_inline_keyboard(buttons)


# === Helper Functions ===

def get_confirmation_keyboard(
    confirm_action: str,
    cancel_action: str = "cancel",
    confirm_text: str = "✅ אשר",
    cancel_text: str = "❌ בטל"
) -> InlineKeyboardMarkup:
    """מקלדת אישור כללית"""
    buttons = [
        [(confirm_text, confirm_action), (cancel_text, cancel_action)]
    ]
    return KeyboardBuilder.build_inline_keyboard(buttons)


def get_rating_keyboard(reference_id: str) -> InlineKeyboardMarkup:
    """מקלדת דירוג (1-5 כוכבים)"""
    buttons = []
    
    # שורת כוכבים
    star_row = []
    for i in range(1, 6):
        stars = "⭐" * i
        star_row.append((stars, f"rate_{i}_{reference_id}"))
    
    buttons.append(star_row)
    buttons.append([("❌ דלג על דירוג", f"skip_rating_{reference_id}")])
    
    return KeyboardBuilder.build_inline_keyboard(buttons)


def get_amount_input_keyboard(
    callback_prefix: str,
    quick_amounts: List[int] = [50, 100, 200, 500, 1000]
) -> InlineKeyboardMarkup:
    """מקלדת בחירת סכום"""
    buttons = []
    
    # סכומים מהירים בשתי עמודות
    for i in range(0, len(quick_amounts), 2):
        row = []
        for j in range(2):
            if i + j < len(quick_amounts):
                amount = quick_amounts[i + j]
                row.append((f"{amount}₪", f"{callback_prefix}_{amount}"))
        buttons.append(row)
    
    buttons.append([("💰 סכום אחר", f"{callback_prefix}_custom")])
    buttons.append([("❌ בטל", "cancel")])
    
    return KeyboardBuilder.build_inline_keyboard(buttons)


def get_timer_info_keyboard(
    dispute_time_left: Optional[str] = None,
    release_time_left: Optional[str] = None
) -> InlineKeyboardMarkup:
    """מקלדת מידע על טיימרים"""
    buttons = []
    
    if dispute_time_left:
        buttons.append([("🚨 זמן לדיווח: " + dispute_time_left, "dispute_timer_info")])
    
    if release_time_left:
        buttons.append([("💰 זמן לשחרור: " + release_time_left, "release_timer_info")])
    
    if not dispute_time_left and not release_time_left:
        buttons.append([("ℹ️ אין טיימרים פעילים", "no_timers")])
    
    buttons.append([("🔙 חזרה", "back")])
    
    return KeyboardBuilder.build_inline_keyboard(buttons)


# === Keyboard Factory ===

class KeyboardFactory:
    """Factory לבחירת המקלדת המתאימה"""
    
    @staticmethod
    def get_keyboard_for_user_role(user_role: UserRole, **kwargs) -> InlineKeyboardMarkup:
        """קבלת מקלדת לפי תפקיד משתמש"""
        if user_role == UserRole.BUYER:
            return MainMenuKeyboards.get_buyer_menu()
        elif user_role == UserRole.SELLER:
            return MainMenuKeyboards.get_seller_menu(**kwargs)
        elif user_role == UserRole.ADMIN:
            return MainMenuKeyboards.get_admin_menu()
        else:
            return MainMenuKeyboards.get_role_selection()
    
    @staticmethod
    def get_dynamic_keyboard(
        keyboard_type: str,
        context_data: Dict,
        **kwargs
    ) -> InlineKeyboardMarkup:
        """יצירת מקלדת דינאמית לפי הקשר"""
        
        keyboard_map = {
            "wallet": WalletKeyboards.get_wallet_menu,
            "categories": CouponKeyboards.get_categories,
            "coupon_actions": CouponKeyboards.get_coupon_actions,
            "order_actions": OrderKeyboards.get_order_actions,
            "auction_actions": AuctionKeyboards.get_auction_actions,
            "dispute_resolution": AdminKeyboards.get_dispute_resolution,
            "pagination": NavigationKeyboards.get_pagination
        }
        
        keyboard_func = keyboard_map.get(keyboard_type)
        if keyboard_func:
            return keyboard_func(**context_data, **kwargs)
        
        # Default fallback
        return MainMenuKeyboards.get_role_selection()
    
    @staticmethod
    def get_order_keyboard_with_timers(
        order_id: str,
        status: OrderStatus,
        is_buyer: bool,
        dispute_window_open: bool = False,
        can_confirm: bool = False,
        dispute_hours_left: Optional[int] = None,
        release_hours_left: Optional[int] = None
    ) -> InlineKeyboardMarkup:
        """מקלדת הזמנה עם טיימרים מדויקים"""
        
        # חישוב זמנים
        dispute_time_str = None
        release_time_str = None
        
        if dispute_hours_left is not None:
            if dispute_hours_left > 0:
                dispute_time_str = f"{dispute_hours_left}h"
            else:
                dispute_time_str = "נסגר"
        
        if release_hours_left is not None:
            if release_hours_left > 0:
                release_time_str = f"{release_hours_left}h"
            else:
                release_time_str = "זמין לשחרור"
        
        return OrderKeyboards.get_order_actions(
            order_id=order_id,
            status=status,
            is_buyer=is_buyer,
            dispute_window_open=dispute_window_open,
            can_confirm=can_confirm,
            time_until_dispute_close=dispute_time_str,
            time_until_auto_release=release_time_str
        )


# TODO: Advanced Keyboard Features
"""
עתיד - תכונות מתקדמות:
- Smart keyboard adaptation based on user behavior
- A/B testing for button layouts
- Accessibility features for disabled users
- Voice command integration
- Gesture-based navigation
- Personalized quick actions
- Context-aware suggestions
- Dynamic button reordering based on usage
"""
