"""
משימות מתוזמנות - APScheduler Tasks
ניהול אוטומטי של טיימרים, התראות ושחרורי כספים
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update
from telegram import Bot
from telegram.error import TelegramError

from app.database import db_manager
from app.models.user import User, Wallet, Transaction, FundLock
from app.models.order import Order, OrderStatus, Auction, AuctionStatus
from app.models.coupon import Coupon, CouponStatus, UserFavorite
from app.services.wallet_service import WalletService
from app.config import settings, MESSAGES

logger = logging.getLogger(__name__)


class SchedulerService:
    """שירות משימות מתוזמנות"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.bot: Optional[Bot] = None
        self._running = False
    
    def setup_scheduler(self) -> AsyncIOScheduler:
        """הגדרת APScheduler עם PostgreSQL jobstore"""
        
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.database_url_sync)
        }
        
        executors = {
            'default': AsyncIOExecutor()
        }
        
        job_defaults = {
            'coalesce': False,
            'max_instances': 3,
            'misfire_grace_time': 30
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        return self.scheduler
    
    async def start(self, telegram_bot: Bot):
        """התחלת השירות"""
        if self._running:
            return
        
        self.bot = telegram_bot
        
        if not self.scheduler:
            self.setup_scheduler()
        
        # הוספת המשימות הקבועות
        await self._add_scheduled_jobs()
        
        self.scheduler.start()
        self._running = True
        logger.info("✅ Scheduler service started")
    
    async def stop(self):
        """עצירת השירות"""
        if self.scheduler and self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("🔒 Scheduler service stopped")
    
    async def _add_scheduled_jobs(self):
        """הוספת כל המשימות המתוזמנות"""
        
        # כל דקה - בדיקות דחופות
        self.scheduler.add_job(
            self.check_urgent_tasks,
            'interval',
            minutes=1,
            id='urgent_tasks',
            replace_existing=True
        )
        
        # כל 5 דקות - שחרור holds ומכרזים
        self.scheduler.add_job(
            self.release_expired_holds,
            'interval',
            minutes=5,
            id='release_holds',
            replace_existing=True
        )
        
        # כל 10 דקות - מכרזים ונעילות
        self.scheduler.add_job(
            self.finalize_ended_auctions,
            'interval',
            minutes=10,
            id='finalize_auctions',
            replace_existing=True
        )
        
        # כל 15 דקות - התראות
        self.scheduler.add_job(
            self.send_notifications,
            'interval',
            minutes=15,
            id='notifications',
            replace_existing=True
        )
        
        # כל שעה - ניקוי ותחזוקה
        self.scheduler.add_job(
            self.cleanup_tasks,
            'interval',
            hours=1,
            id='cleanup',
            replace_existing=True
        )
        
        # יומי - משימות יומיות
        self.scheduler.add_job(
            self.daily_tasks,
            'cron',
            hour=2,
            minute=0,
            id='daily_tasks',
            replace_existing=True
        )
        
        logger.info("📅 Scheduled jobs added successfully")
    
    # === משימות דחופות (כל דקה) ===
    
    async def check_urgent_tasks(self):
        """בדיקות דחופות שצריכות לרוץ כל דקה"""
        try:
            async with db_manager.get_session() as session:
                # בדיקת מכרזים שמסתיימים בדקות הקרובות
                await self._check_ending_auctions_soon(session)
                
                # בדיקת חלונות דיווח שנסגרים בקרוב  
                await self._check_dispute_windows_closing(session)
        
        except Exception as e:
            logger.error(f"❌ Urgent tasks failed: {e}")
    
    async def _check_ending_auctions_soon(self, session: AsyncSession):
        """בדיקת מכרזים שמסתיימים ב-10 דקות הקרובות"""
        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=10)
        
        stmt = select(Auction).where(
            and_(
                Auction.status == AuctionStatus.ACTIVE,
                or_(
                    and_(Auction.extended_until.is_(None), Auction.ends_at <= soon),
                    and_(Auction.extended_until.isnot(None), Auction.extended_until <= soon)
                )
            )
        )
        
        result = await session.execute(stmt)
        ending_auctions = result.scalars().all()
        
        for auction in ending_auctions:
            await self._notify_auction_ending_soon(auction)
    
    async def _check_dispute_windows_closing(self, session: AsyncSession):
        """בדיקת חלונות דיווח שנסגרים בשעתיים הקרובות"""
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=2)
        
        stmt = select(Order).where(
            and_(
                Order.status == OrderStatus.DELIVERED,
                Order.dispute_window_until.isnot(None),
                Order.dispute_window_until <= soon,
                Order.dispute_window_until > now,
                Order.reported_at.is_(None)  # עדיין לא דווח
            )
        )
        
        result = await session.execute(stmt)
        closing_windows = result.scalars().all()
        
        for order in closing_windows:
            await self._send_dispute_window_reminder(order)
    
    # === שחרור Holds (כל 5 דקות) ===
    
    async def release_expired_holds(self):
        """שחרור holds שהגיע זמנם"""
        try:
            async with db_manager.get_session() as session:
                wallet_service = WalletService(session)
                
                # קבלת הזמנות שמוכנות לשחרור
                orders_to_release = await wallet_service.get_orders_ready_for_release()
                
                released_count = 0
                for order_id in orders_to_release:
                    # קבלת פרטי ההזמנה
                    stmt = select(Order).where(Order.id == order_id)
                    result = await session.execute(stmt)
                    order = result.scalar_one_or_none()
                    
                    if order and order.status == OrderStatus.DELIVERED:
                        # שחרור ה-hold למוכר
                        success = await wallet_service.release_seller_hold(
                            order_id=order_id,
                            seller_id=order.seller_id,
                            early_release=False
                        )
                        
                        if success:
                            # עדכון סטטוס ההזמנה
                            order.status = OrderStatus.RELEASED
                            await session.commit()
                            
                            # הודעה למוכר
                            await self._notify_seller_payment_released(order)
                            released_count += 1
                
                if released_count > 0:
                    logger.info(f"✅ Released {released_count} seller holds")
                
                # ניקוי נעילות שפגו
                expired_cleaned = await wallet_service.cleanup_expired_locks()
                if expired_cleaned > 0:
                    logger.info(f"🧹 Cleaned {expired_cleaned} expired fund locks")
        
        except Exception as e:
            logger.error(f"❌ Hold release failed: {e}")
    
    # === סיום מכרזים (כל 10 דקות) ===
    
    async def finalize_ended_auctions(self):
        """סיום מכרזים שהסתיימו"""
        try:
            async with db_manager.get_session() as session:
                now = datetime.now(timezone.utc)
                
                # קבלת מכרזים שהסתיימו אבל עדיין לא סופיים
                stmt = select(Auction).where(
                    and_(
                        Auction.status == AuctionStatus.ACTIVE,
                        or_(
                            and_(Auction.extended_until.is_(None), Auction.ends_at <= now),
                            and_(Auction.extended_until.isnot(None), Auction.extended_until <= now)
                        )
                    )
                )
                
                result = await session.execute(stmt)
                ended_auctions = result.scalars().all()
                
                for auction in ended_auctions:
                    await self._finalize_auction(session, auction)
        
        except Exception as e:
            logger.error(f"❌ Auction finalization failed: {e}")
    
    async def _finalize_auction(self, session: AsyncSession, auction: Auction):
        """סיום מכרז בודד"""
        try:
            # עדכון סטטוס לסיום
            auction.status = AuctionStatus.ENDED
            
            # אם יש זוכה
            if auction.winner_id and auction.winning_bid_id:
                wallet_service = WalletService(session)
                
                # יצירת הזמנה מהמכרז
                from app.models.order import create_auction_order
                from app.models.coupon import Coupon
                
                # קבלת פרטי הקופון
                stmt = select(Coupon).where(Coupon.id == auction.coupon_id)
                result = await session.execute(stmt)
                coupon = result.scalar_one()
                
                if coupon:
                    # חיוב הזוכה ויצירת הזמנה
                    seller_verified = await self._is_seller_verified(session, auction.seller_id)
                    
                    buyer_tx, seller_tx = await wallet_service.finalize_auction(
                        auction_id=auction.id,
                        winner_id=auction.winner_id,
                        winning_amount=auction.current_price,
                        seller_id=auction.seller_id,
                        seller_verified=seller_verified
                    )
                    
                    # עדכון סטטוס למכרז כסופי
                    auction.status = AuctionStatus.FINALIZED
                    auction.finalized_at = datetime.now(timezone.utc)
                    
                    # הודעות למשתתפים
                    await self._notify_auction_winner(auction)
                    await self._notify_auction_losers(auction)
                    
                    logger.info(f"✅ Auction {auction.id} finalized, winner: {auction.winner_id}")
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"❌ Failed to finalize auction {auction.id}: {e}")
            await session.rollback()
    
    # === התראות (כל 15 דקות) ===
    
    async def send_notifications(self):
        """שליחת התראות למשתמשים"""
        try:
            async with db_manager.get_session() as session:
                await self._send_price_drop_notifications(session)
                await self._send_expiry_notifications(session)
                await self._send_favorite_notifications(session)
        
        except Exception as e:
            logger.error(f"❌ Notifications failed: {e}")
    
    async def _send_price_drop_notifications(self, session: AsyncSession):
        """התראות על ירידת מחיר"""
        # קבלת מועדפים שראוי לשלוח עליהם התראה
        stmt = select(UserFavorite).join(Coupon).where(
            and_(
                UserFavorite.notify_price_drop == True,
                Coupon.status == CouponStatus.ACTIVE
            )
        )
        
        result = await session.execute(stmt)
        favorites = result.scalars().all()
        
        sent_count = 0
        for favorite in favorites:
            if favorite.should_notify_price_drop(
                favorite.coupon.selling_price, 
                settings.PRICE_DROP_THRESHOLD_PERCENT
            ):
                await self._send_telegram_notification(
                    user_id=favorite.user_id,
                    message=f"💸 ירד מחיר! {favorite.coupon.title}\nמחיר חדש: {favorite.coupon.selling_price}₪"
                )
                
                # עדכון שנשלחה התראה
                favorite.price_alerts_sent += 1
                favorite.last_price_check = datetime.now(timezone.utc)
                sent_count += 1
        
        if sent_count > 0:
            await session.commit()
            logger.info(f"📢 Sent {sent_count} price drop notifications")
    
    async def _send_expiry_notifications(self, session: AsyncSession):
        """התראות על קופונים שפגים בקרוב"""
        # קופונים שפגים בשבוע הקרוב
        soon = datetime.now(timezone.utc) + timedelta(days=7)
        
        stmt = select(UserFavorite).join(Coupon).where(
            and_(
                UserFavorite.notify_expiry == True,
                Coupon.status == CouponStatus.ACTIVE,
                Coupon.expires_at.isnot(None),
                Coupon.expires_at <= soon
            )
        )
        
        result = await session.execute(stmt)
        expiring_favorites = result.scalars().all()
        
        for favorite in expiring_favorites:
            days_left = (favorite.coupon.expires_at - datetime.now(timezone.utc)).days
            
            await self._send_telegram_notification(
                user_id=favorite.user_id,
                message=f"⏰ קופון פג בקרוב!\n{favorite.coupon.title}\nנותרו {days_left} ימים"
            )
    
    # === משימות ניקוי (כל שעה) ===
    
    async def cleanup_tasks(self):
        """משימות ניקוי ותחזוקה"""
        try:
            async with db_manager.get_session() as session:
                await self._cleanup_expired_coupons(session)
                await self._update_seller_daily_quotas(session)
                await self._cleanup_old_transactions(session)
        
        except Exception as e:
            logger.error(f"❌ Cleanup tasks failed: {e}")
    
    async def _cleanup_expired_coupons(self, session: AsyncSession):
        """עדכון קופונים שפגו"""
        now = datetime.now(timezone.utc)
        
        stmt = update(Coupon).where(
            and_(
                Coupon.status == CouponStatus.ACTIVE,
                Coupon.expires_at.isnot(None),
                Coupon.expires_at <= now
            )
        ).values(status=CouponStatus.EXPIRED)
        
        result = await session.execute(stmt)
        expired_count = result.rowcount
        
        if expired_count > 0:
            await session.commit()
            logger.info(f"🗑️ Marked {expired_count} coupons as expired")
    
    async def _update_seller_daily_quotas(self, session: AsyncSession):
        """איפוס מונים יומיים של מוכרים"""
        from app.models.user import SellerProfile
        
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # איפוס מוכרים שהיום שלהם התחדש
        stmt = update(SellerProfile).where(
            SellerProfile.quota_reset_date < today_start
        ).values(
            daily_count=0,
            quota_reset_date=today_start
        )
        
        result = await session.execute(stmt)
        reset_count = result.rowcount
        
        if reset_count > 0:
            await session.commit()
            logger.info(f"🔄 Reset daily quota for {reset_count} sellers")
    
    # === משימות יומיות ===
    
    async def daily_tasks(self):
        """משימות שרצות פעם ביום"""
        try:
            async with db_manager.get_session() as session:
                await self._generate_daily_reports(session)
                await self._cleanup_old_data(session)
                await self._backup_important_data(session)
        
        except Exception as e:
            logger.error(f"❌ Daily tasks failed: {e}")
    
    async def _generate_daily_reports(self, session: AsyncSession):
        """יצירת דוחות יומיים"""
        # TODO: יצירת דוחות למערכת ואדמינים
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        # ספירת עסקאות יום קודם
        stmt = select(Order).where(
            and_(
                Order.created_at >= yesterday,
                Order.status.in_([OrderStatus.DELIVERED, OrderStatus.RELEASED])
            )
        )
        
        result = await session.execute(stmt)
        daily_orders = len(list(result.scalars().all()))
        
        if settings.LOG_CHANNEL_ID and daily_orders > 0:
            await self._send_admin_notification(
                f"📊 דוח יומי\nעסקאות אתמול: {daily_orders}"
            )
    
    # === Helper Functions ===
    
    async def _send_telegram_notification(self, user_id: int, message: str):
        """שליחת התראה לטלגרם"""
        if not self.bot:
            return
        
        try:
            # קבלת telegram_user_id
            async with db_manager.get_session() as session:
                stmt = select(User.telegram_user_id).where(User.id == user_id)
                result = await session.execute(stmt)
                telegram_user_id = result.scalar_one_or_none()
                
                if telegram_user_id:
                    await self.bot.send_message(
                        chat_id=telegram_user_id,
                        text=message
                    )
        
        except TelegramError as e:
            logger.warning(f"Failed to send notification to user {user_id}: {e}")
    
    async def _send_admin_notification(self, message: str):
        """שליחת התראה לאדמינים"""
        if not self.bot or not settings.ADMIN_CHAT_IDS:
            return
        
        for admin_chat_id in settings.ADMIN_CHAT_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🔔 {message}"
                )
            except TelegramError as e:
                logger.warning(f"Failed to send admin notification: {e}")
    
    async def _is_seller_verified(self, session: AsyncSession, seller_id: int) -> bool:
        """בדיקה האם מוכר מאומת"""
        from app.models.user import SellerProfile
        
        stmt = select(SellerProfile.is_verified).where(
            SellerProfile.user_id == seller_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() or False
    
    async def _notify_auction_ending_soon(self, auction: Auction):
        """התראה על מכרז שמסתיים בקרוב"""
        # TODO: הודעה לכל המשתתפים במכרז
        pass
    
    async def _send_dispute_window_reminder(self, order: Order):
        """תזכורת לפני סגירת חלון דיווח"""
        message = (
            f"⏰ תזכורת: חלון דיווח נסגר בעוד שעתיים!\n"
            f"הזמנה: {order.id}\n"
            f"אם יש בעיה עם הקופון, דווח עכשיו 🚨"
        )
        
        await self._send_telegram_notification(order.buyer_id, message)
    
    async def _notify_seller_payment_released(self, order: Order):
        """הודעה למוכר על שחרור תשלום"""
        message = (
            f"💰 התשלום שוחרר!\n"
            f"הזמנה: {order.id}\n"
            f"סכום: {order.seller_amount_net}₪"
        )
        
        await self._send_telegram_notification(order.seller_id, message)
    
    async def _notify_auction_winner(self, auction: Auction):
        """הודעה לזוכה במכרז"""
        message = (
            f"🎉 זכית במכרז!\n"
            f"סכום זכייה: {auction.current_price}₪\n"
            f"הקופון יישלח אליך בקרוב"
        )
        
        await self._send_telegram_notification(auction.winner_id, message)
    
    async def _notify_auction_losers(self, auction: Auction):
        """הודעה למפסידים במכרז"""
        # TODO: שליחת הודעות לכל המפסידים
        pass
    
    async def _cleanup_old_transactions(self, session: AsyncSession):
        """ניקוי תנועות ישנות (שמירה של 1 שנה)"""
        # TODO: ארכיון או מחיקה של תנועות ישנות מאוד
        pass
    
    async def _cleanup_old_data(self, session: AsyncSession):
        """ניקוי נתונים ישנים"""
        # TODO: מחיקת לוגים ישנים, sessions פגות, etc.
        pass
    
    async def _backup_important_data(self, session: AsyncSession):
        """גיבוי נתונים חשובים"""
        # TODO: גיבוי נתונים קריטיים
        pass


# === Global Scheduler Instance ===

scheduler_service = SchedulerService()


# === Startup/Shutdown Functions ===

async def start_scheduler(telegram_bot: Bot):
    """התחלת השירות המתוזמן"""
    await scheduler_service.start(telegram_bot)


async def stop_scheduler():
    """עצירת השירות המתוזמן"""
    await scheduler_service.stop()


# === Manual Task Triggers (for testing) ===

async def trigger_hold_release():
    """הפעלה ידנית של שחרור holds"""
    await scheduler_service.release_expired_holds()


async def trigger_auction_finalization():
    """הפעלה ידנית של סיום מכרזים"""
    await scheduler_service.finalize_ended_auctions()


async def trigger_notifications():
    """הפעלה ידנית של התראות"""
    await scheduler_service.send_notifications()


# TODO: Advanced Scheduler Features
"""
עתיד - תכונות מתקדמות:
- Smart scheduling based on user activity patterns
- A/B testing for notification timing
- Machine learning for optimal auction timing
- Predictive analytics for demand forecasting
- Dynamic pricing suggestions
- Fraud detection patterns
- Performance monitoring and alerting
"""
