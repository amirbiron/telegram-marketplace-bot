#!/usr/bin/env python3
"""
נקודת הכניסה הראשית - Main Entry Point
בוט טלגרם Marketplace לקופונים וכרטיסים
"""

import asyncio
import logging
import logging.config
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

# Third party imports
from telegram import Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Local imports
from app.config import settings, LOGGING_CONFIG
from app.database import init_database, close_database, health_check
from app.models.coupon import initialize_default_categories
from app.scheduler.tasks import start_scheduler, stop_scheduler
from app.bot.handlers.main import (
    get_main_conversation_handler,
    MenuHandlers,
    WalletHandlers, 
    CouponHandlers,
    SystemHandlers,
    error_handler
)

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


class TelegramBot:
    """מנהל בוט הטלגרם"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self._running = False
    
    async def initialize(self) -> None:
        """אתחול הבוט"""
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        # יצירת Application
        self.application = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .build()
        )
        
        self.bot = self.application.bot
        
        # הוספת handlers
        self._add_handlers()
        
        logger.info("✅ Telegram bot initialized")
    
    def _add_handlers(self) -> None:
        """הוספת כל ה-handlers לבוט"""
        app = self.application
        
        # Main conversation handler
        app.add_handler(get_main_conversation_handler())
        
        # Menu handlers  
        app.add_handler(CallbackQueryHandler(
            MenuHandlers.buyer_menu_callback, 
            pattern='^buyer_menu$'
        ))
        app.add_handler(CallbackQueryHandler(
            MenuHandlers.seller_menu_callback,
            pattern='^seller_menu$'
        ))
        app.add_handler(CallbackQueryHandler(
            MenuHandlers.admin_menu_callback,
            pattern='^admin_menu$'
        ))
        
        # Wallet handlers
        app.add_handler(CallbackQueryHandler(
            WalletHandlers.wallet_menu_callback,
            pattern='^wallet_menu$'
        ))
        app.add_handler(CallbackQueryHandler(
            WalletHandlers.add_balance_callback,
            pattern='^add_balance$'
        ))
        app.add_handler(CallbackQueryHandler(
            WalletHandlers.refresh_balance_callback,
            pattern='^refresh_balance$'
        ))
        
        # Coupon handlers
        app.add_handler(CallbackQueryHandler(
            CouponHandlers.browse_coupons_callback,
            pattern='^browse_coupons$'
        ))
        app.add_handler(CallbackQueryHandler(
            CouponHandlers.category_callback,
            pattern='^category_'
        ))
        
        # System handlers
        app.add_handler(CallbackQueryHandler(
            SystemHandlers.contact_support_callback,
            pattern='^contact_support$'
        ))
        app.add_handler(CallbackQueryHandler(
            SystemHandlers.terms_policy_callback,
            pattern='^terms_policy$'
        ))
        
        # Back navigation handlers
        app.add_handler(CallbackQueryHandler(
            MenuHandlers.buyer_menu_callback,
            pattern='^back_to_main$'
        ))
        
        # Generic back handlers based on user role
        app.add_handler(CallbackQueryHandler(
            self._handle_back_navigation,
            pattern='^back_'
        ))
        
        # Unknown callback handler (fallback)
        app.add_handler(CallbackQueryHandler(
            SystemHandlers.unknown_callback
        ))
        
        # Error handler
        app.add_error_handler(error_handler)
        
        logger.info("📋 Bot handlers registered")
    
    async def _handle_back_navigation(self, update, context):
        """טיפול בניווט חזרה דינאמי"""
        query = update.callback_query
        await query.answer()
        
        user_role = context.user_data.get('role')
        
        if user_role == 'BUYER':
            await MenuHandlers.buyer_menu_callback(update, context)
        elif user_role == 'SELLER':
            await MenuHandlers.seller_menu_callback(update, context)
        elif user_role == 'ADMIN':
            await MenuHandlers.admin_menu_callback(update, context)
        else:
            from app.bot.keyboards import MainMenuKeyboards
            keyboard = MainMenuKeyboards.get_role_selection()
            await query.edit_message_text(
                "🏠 בחר תפקיד:",
                reply_markup=keyboard
            )
    
    async def start(self) -> None:
        """הפעלת הבוט"""
        if not self.application:
            await self.initialize()
        
        logger.info("🚀 Starting Telegram bot...")
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        self._running = True
        logger.info("✅ Telegram bot started successfully")
    
    async def stop(self) -> None:
        """עצירת הבוט"""
        if self.application and self._running:
            logger.info("🔒 Stopping Telegram bot...")
            
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
            self._running = False
            logger.info("✅ Telegram bot stopped")


class WebAPI:
    """FastAPI web server למנהל ואינטגרציות"""
    
    def __init__(self, telegram_bot: TelegramBot):
        self.telegram_bot = telegram_bot
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """יצירת FastAPI application"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info("🌐 FastAPI starting up...")
            
            await init_database()
            
            try:
                from app.database import db_manager
                async with db_manager.get_session() as session:
                    categories = initialize_default_categories()
                    for category in categories:
                        session.add(category)
                    await session.commit()
                    logger.info("📂 Default categories initialized")
            except Exception as e:
                logger.warning(f"Categories initialization warning: {e}")
            
            if self.telegram_bot.bot:
                await start_scheduler(self.telegram_bot.bot)
            
            yield
            
            # Shutdown
            logger.info("🔒 FastAPI shutting down...")
            await stop_scheduler()
            await close_database()
        
        app = FastAPI(
            title=settings.APP_NAME,
            version=settings.VERSION,
            description="Telegram Marketplace Bot for Coupons & Tickets",
            lifespan=lifespan
        )
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if settings.is_development else [],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.get("/health")
        async def health_endpoint():
            db_health = await health_check()
            
            return {
                "status": "healthy" if db_health["healthy"] else "unhealthy",
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "database": db_health,
                "telegram_bot": {
                    "running": self.telegram_bot._running,
                    "token_configured": bool(settings.TELEGRAM_BOT_TOKEN)
                }
            }
        
        @app.get("/")
        async def root():
            return {
                "service": settings.APP_NAME,
                "version": settings.VERSION,
                "status": "running",
                "endpoints": {
                    "health": "/health",
                    "docs": "/docs"
                }
            }
        
        logger.info("📡 FastAPI app created")
        return app
    
    def run(self, host: str = None, port: int = None):
        uvicorn.run(
            self.app,
            host=host or settings.HOST,
            port=port or settings.PORT,
            log_config=None
        )


class MarketplaceApp:
    """האפליקציה הראשית"""
    
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.web_api = WebAPI(self.telegram_bot)
        self._shutdown_event = asyncio.Event()
        
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"📡 Received signal {signum}")
        self._shutdown_event.set()
    
    async def run_bot_only(self):
        """הרצת בוט בלבד (למודים production)"""
        try:
            logger.info("🤖 Starting bot-only mode...")
            
            await init_database()
            
            try:
                from app.database import db_manager
                async with db_manager.get_session() as session:
                    categories = initialize_default_categories()
                    for category in categories:
                        session.add(category)
                    await session.commit()
                    logger.info("📂 Categories initialized")
            except Exception as e:
                logger.warning(f"Categories init warning: {e}")
            
            await self.telegram_bot.start()
            
            if self.telegram_bot.bot:
                await start_scheduler(self.telegram_bot.bot)
            
            logger.info(f"🎉 {settings.APP_NAME} v{settings.VERSION} is running!")
            
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"❌ Application failed: {e}")
            raise
        
        finally:
            await self.shutdown()
    
    async def run_with_api(self):
        """הרצה עם FastAPI (למודים development)"""
        try:
            logger.info("🌐 Starting full mode (bot + API)...")
            
            await self.telegram_bot.start()
            
            logger.info(f"🎉 {settings.APP_NAME} v{settings.VERSION} starting with API...")
            
            self.web_api.run()
            
        except Exception as e:
            logger.error(f"❌ Application failed: {e}")
            raise
        
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """עצירה נקייה"""
        logger.info("🔄 Shutting down application...")
        
        try:
            await stop_scheduler()
            await self.telegram_bot.stop()
            await close_database()
            
            logger.info("✅ Application shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")


async def run_bot():
    """הרצת בוט בלבד"""
    app = MarketplaceApp()
    await app.run_bot_only()


async def run_with_api():
    """הרצה עם API"""
    app = MarketplaceApp()
    await app.run_with_api()


def main():
    """נקודת כניסה ראשית"""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"📍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🗄️ Database configured")
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "api":
            asyncio.run(run_with_api())
        else:
            asyncio.run(run_bot())
    
    except KeyboardInterrupt:
        logger.info("👋 Application interrupted by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)


async def test_database():
    """בדיקת חיבור מסד נתונים"""
    try:
        await init_database()
        health = await health_check()
        
        if health["healthy"]:
            logger.info("✅ Database connection successful")
            print("Database Status:", health)
        else:
            logger.error("❌ Database connection failed")
            print("Database Error:", health)
        
        await close_database()
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")


async def init_categories():
    """אתחול קטגוריות בלבד"""
    try:
        await init_database()
        
        from app.database import db_manager
        async with db_manager.get_session() as session:
            categories = initialize_default_categories()
            for category in categories:
                session.add(category)
            await session.commit()
            
        logger.info("✅ Categories initialized successfully")
        await close_database()
        
    except Exception as e:
        logger.error(f"Categories initialization failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test-db":
            asyncio.run(test_database())
        elif command == "init-categories":
            asyncio.run(init_categories())
        elif command == "api":
            main()
        else:
            print("Available commands:")
            print("  python main.py          - Run bot only")
            print("  python main.py api      - Run with FastAPI")  
            print("  python main.py test-db  - Test database connection")
            print("  python main.py init-categories - Initialize categories")
    else:
        main()
