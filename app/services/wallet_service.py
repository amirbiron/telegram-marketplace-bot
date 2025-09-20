"""
שירות ארנקים - Wallet Service
לוגיקה עסקית מלאה לניהול יתרות, נעילות ועסקאות
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Tuple, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import selectinload

from app.models.user import (
    User, Wallet, Transaction, FundLock, 
    TransactionType, calculate_fees
)
from app.models.order import Order, OrderStatus
from app.config import settings

logger = logging.getLogger(__name__)


class WalletServiceError(Exception):
    """שגיאות בשירות ארנקים"""
    pass


class InsufficientFundsError(WalletServiceError):
    """יתרה לא מספקת"""
    pass


class WalletService:
    """שירות ניהול ארנקים עם תמיכה מלאה בנעילות ו-holds"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Basic Wallet Operations ===
    
    async def get_wallet(self, user_id: int) -> Optional[Wallet]:
        """קבלת ארנק משתמש"""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_wallet(self, user_id: int) -> Wallet:
        """יצירת ארנק חדש"""
        wallet = Wallet(
            user_id=user_id,
            total_balance=Decimal('0.00'),
            locked_balance=Decimal('0.00')
        )
        self.session.add(wallet)
        await self.session.flush()
        return wallet
    
    async def get_or_create_wallet(self, user_id: int) -> Wallet:
        """קבלת ארנק או יצירה אם לא קיים"""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            wallet = await self.create_wallet(user_id)
        return wallet
    
    # === Balance Display (UI Helper) ===
    
    async def get_balance_display(self, user_id: int) -> Dict[str, Decimal]:
        """
        קבלת יתרות לתצוגה
        Returns: {"total": xxx, "locked": xxx, "available": xxx}
        """
        wallet = await self.get_or_create_wallet(user_id)
        return {
            "total": wallet.total_balance,      # 💰 כוללת
            "locked": wallet.locked_balance,    # 🔒 קפואה
            "available": wallet.available_balance  # ✅ זמינה
        }
    
    # === Transaction Management ===
    
    async def create_transaction(
        self,
        wallet: Wallet,
        transaction_type: TransactionType,
        amount: Decimal,
        description: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[str] = None,
        admin_id: Optional[int] = None
    ) -> Transaction:
        """יצירת רשומת תנועה עם עדכון יתרות"""
        
        # שמירת יתרות לפני השינוי
        balance_before = wallet.total_balance
        locked_before = wallet.locked_balance
        
        # עדכון יתרות לפי סוג התנועה
        if transaction_type in [
            TransactionType.DEPOSIT, 
            TransactionType.SALE_CREDIT, 
            TransactionType.REFUND,
            TransactionType.SYSTEM_ADJUSTMENT
        ]:
            # זיכוי
            wallet.total_balance += amount
            
        elif transaction_type in [
            TransactionType.PURCHASE_DEBIT, 
            TransactionType.WITHDRAWAL, 
            TransactionType.FEE_DEBIT
        ]:
            # חיוב
            if wallet.available_balance < amount:
                raise InsufficientFundsError(f"Insufficient funds: need {amount}, have {wallet.available_balance}")
            wallet.total_balance -= amount
            
        elif transaction_type == TransactionType.LOCK:
            # נעילת כספים
            if wallet.available_balance < amount:
                raise InsufficientFundsError(f"Cannot lock {amount}, available: {wallet.available_balance}")
            wallet.locked_balance += amount
            
        elif transaction_type == TransactionType.RELEASE:
            # שחרור נעילה
            wallet.locked_balance -= amount
            
        elif transaction_type == TransactionType.HOLD_LOCK:
            # נעילה למוכר (לא משפיע על total - כבר נוכה)
            wallet.locked_balance += amount
            
        elif transaction_type == TransactionType.HOLD_RELEASE:
            # שחרור hold למוכר
            wallet.locked_balance -= amount
            wallet.total_balance += amount  # זיכוי למוכר
        
        # יצירת רשומת התנועה
        transaction = Transaction(
            user_id=wallet.user_id,
            wallet_id=wallet.id,
            type=transaction_type,
            amount=amount,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata,
            processed_by_admin_id=admin_id,
            balance_before=balance_before,
            balance_after=wallet.total_balance,
            locked_before=locked_before,
            locked_after=wallet.locked_balance
        )
        
        self.session.add(transaction)
        await self.session.flush()
        
        logger.info(f"Transaction created: {transaction_type.value} {amount} for user {wallet.user_id}")
        return transaction
    
    # === Fund Locks Management ===
    
    async def create_fund_lock(
        self,
        user_id: int,
        amount: Decimal,
        reason: str,
        reference_type: str,
        reference_id: str,
        expires_at: Optional[datetime] = None
    ) -> FundLock:
        """יצירת נעילת כספים"""
        wallet = await self.get_or_create_wallet(user_id)
        
        # בדיקת יתרה זמינה
        if not wallet.can_afford(amount):
            raise InsufficientFundsError(
                f"Cannot lock {amount}₪, available: {wallet.available_balance}₪"
            )
        
        # יצירת הנעילה
        fund_lock = FundLock(
            user_id=user_id,
            wallet_id=wallet.id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            expires_at=expires_at
        )
        
        # יצירת תנועה לנעילה
        await self.create_transaction(
            wallet=wallet,
            transaction_type=TransactionType.LOCK,
            amount=amount,
            description=f"נעילת כספים: {reason}",
            reference_type=reference_type,
            reference_id=reference_id
        )
        
        self.session.add(fund_lock)
        await self.session.flush()
        
        logger.info(f"Fund lock created: {amount}₪ for user {user_id}, reason: {reason}")
        return fund_lock
    
    async def release_fund_lock(
        self, 
        lock_id: str, 
        admin_id: Optional[int] = None
    ) -> bool:
        """שחרור נעילת כספים"""
        stmt = select(FundLock).where(
            and_(FundLock.id == lock_id, FundLock.is_active == True)
        )
        result = await self.session.execute(stmt)
        fund_lock = result.scalar_one_or_none()
        
        if not fund_lock:
            return False
        
        # עדכון הנעילה כלא פעילה
        fund_lock.is_active = False
        fund_lock.released_at = datetime.now(timezone.utc)
        
        # קבלת הארנק ושחרור הכספים
        wallet = await self.get_wallet(fund_lock.user_id)
        if wallet:
            await self.create_transaction(
                wallet=wallet,
                transaction_type=TransactionType.RELEASE,
                amount=fund_lock.amount,
                description=f"שחרור נעילה: {fund_lock.reason}",
                reference_type=fund_lock.reference_type,
                reference_id=fund_lock.reference_id,
                admin_id=admin_id
            )
        
        logger.info(f"Fund lock released: {lock_id}, amount: {fund_lock.amount}₪")
        return True
    
    async def update_fund_lock_amount(
        self, 
        lock_id: str, 
        new_amount: Decimal
    ) -> bool:
        """עדכון סכום נעילה (למכרזים - הצעה חדשה)"""
        stmt = select(FundLock).where(
            and_(FundLock.id == lock_id, FundLock.is_active == True)
        )
        result = await self.session.execute(stmt)
        fund_lock = result.scalar_one_or_none()
        
        if not fund_lock:
            return False
        
        wallet = await self.get_wallet(fund_lock.user_id)
        old_amount = fund_lock.amount
        amount_diff = new_amount - old_amount
        
        if amount_diff > 0:
            # נעילה נוספת
            if not wallet.can_afford(amount_diff):
                raise InsufficientFundsError(
                    f"Cannot lock additional {amount_diff}₪"
                )
            
            await self.create_transaction(
                wallet=wallet,
                transaction_type=TransactionType.LOCK,
                amount=amount_diff,
                description=f"הגדלת נעילה: {fund_lock.reason}",
                reference_type=fund_lock.reference_type,
                reference_id=fund_lock.reference_id
            )
        
        elif amount_diff < 0:
            # שחרור חלקי
            await self.create_transaction(
                wallet=wallet,
                transaction_type=TransactionType.RELEASE,
                amount=abs(amount_diff),
                description=f"הקטנת נעילה: {fund_lock.reason}",
                reference_type=fund_lock.reference_type,
                reference_id=fund_lock.reference_id
            )
        
        fund_lock.amount = new_amount
        return True
    
    # === Purchase Flow ===
    
    async def process_purchase(
        self,
        buyer_id: int,
        seller_id: int,
        total_amount: Decimal,
        order_id: str,
        seller_verified: bool = False
    ) -> Tuple[Transaction, Transaction]:
        """
        עיבוד רכישה מלא:
        1. חיוב קונה (כולל עמלה)
        2. נעילת hold למוכר
        """
        buyer_fee, seller_fee = calculate_fees(
            total_amount, 
            is_buyer=True, 
            seller_verified=seller_verified
        )
        
        buyer_total = total_amount + buyer_fee
        seller_net = total_amount - seller_fee
        
        # חיוב הקונה
        buyer_wallet = await self.get_or_create_wallet(buyer_id)
        buyer_transaction = await self.create_transaction(
            wallet=buyer_wallet,
            transaction_type=TransactionType.PURCHASE_DEBIT,
            amount=buyer_total,
            description=f"רכישת קופון (כולל עמלה {buyer_fee}₪)",
            reference_type="order",
            reference_id=order_id
        )
        
        # Hold למוכר (יזוכה אחרי 24h או אישור מוקדם)
        seller_wallet = await self.get_or_create_wallet(seller_id)
        seller_transaction = await self.create_transaction(
            wallet=seller_wallet,
            transaction_type=TransactionType.HOLD_LOCK,
            amount=seller_net,
            description=f"החזקת תשלום למוכר (נטו {seller_net}₪)",
            reference_type="order",
            reference_id=order_id
        )
        
        logger.info(f"Purchase processed: buyer={buyer_id} paid {buyer_total}₪, seller={seller_id} hold {seller_net}₪")
        return buyer_transaction, seller_transaction
    
    async def release_seller_hold(
        self, 
        order_id: str, 
        seller_id: int,
        early_release: bool = False,
        admin_id: Optional[int] = None
    ) -> bool:
        """שחרור hold למוכר"""
        seller_wallet = await self.get_or_create_wallet(seller_id)
        
        # חיפוש hold transaction
        stmt = select(Transaction).where(
            and_(
                Transaction.wallet_id == seller_wallet.id,
                Transaction.type == TransactionType.HOLD_LOCK,
                Transaction.reference_type == "order",
                Transaction.reference_id == order_id
            )
        )
        result = await self.session.execute(stmt)
        hold_transaction = result.scalar_one_or_none()
        
        if not hold_transaction:
            logger.warning(f"No hold transaction found for order {order_id}")
            return False
        
        # שחרור ה-hold
        release_reason = "אישור מוקדם של הקונה" if early_release else "שחרור אוטומטי (24h)"
        
        await self.create_transaction(
            wallet=seller_wallet,
            transaction_type=TransactionType.HOLD_RELEASE,
            amount=hold_transaction.amount,
            description=f"שחרור תשלום למוכר: {release_reason}",
            reference_type="order",
            reference_id=order_id,
            admin_id=admin_id
        )
        
        logger.info(f"Seller hold released: order={order_id}, amount={hold_transaction.amount}₪")
        return True
    
    # === Auction Flow ===
    
    async def place_auction_bid(
        self,
        bidder_id: int,
        auction_id: str,
        bid_amount: Decimal,
        previous_bid_lock_id: Optional[str] = None
    ) -> FundLock:
        """הגשת הצעה במכרז עם נעילת כספים"""
        
        # שחרור נעילה קודמת (אם יש)
        if previous_bid_lock_id:
            await self.release_fund_lock(previous_bid_lock_id)
        
        # נעילה חדשה לסכום ההצעה
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)  # נעילה למשך זמן המכרז + רזרבה
        
        fund_lock = await self.create_fund_lock(
            user_id=bidder_id,
            amount=bid_amount,
            reason=f"הצעה במכרז",
            reference_type="auction",
            reference_id=auction_id,
            expires_at=expires_at
        )
        
        return fund_lock
    
    async def finalize_auction(
        self,
        auction_id: str,
        winner_id: int,
        winning_amount: Decimal,
        seller_id: int,
        seller_verified: bool = False
    ) -> Tuple[Transaction, Transaction]:
        """סיום מכרז וחיוב הזוכה"""
        
        # שחרור כל הנעילות של המכרז (למפסידים)
        await self.release_auction_losing_bids(auction_id, winner_id)
        
        # חיוב הזוכה (כמו רכישה רגילה)
        buyer_transaction, seller_transaction = await self.process_purchase(
            buyer_id=winner_id,
            seller_id=seller_id,
            total_amount=winning_amount,
            order_id=f"auction_{auction_id}",
            seller_verified=seller_verified
        )
        
        return buyer_transaction, seller_transaction
    
    async def release_auction_losing_bids(
        self, 
        auction_id: str, 
        winner_id: int
    ) -> int:
        """שחרור נעילות המפסידים במכרז"""
        stmt = select(FundLock).where(
            and_(
                FundLock.reference_type == "auction",
                FundLock.reference_id == auction_id,
                FundLock.user_id != winner_id,
                FundLock.is_active == True
            )
        )
        result = await self.session.execute(stmt)
        losing_locks = result.scalars().all()
        
        count = 0
        for lock in losing_locks:
            await self.release_fund_lock(lock.id)
            count += 1
        
        logger.info(f"Released {count} losing auction bids for auction {auction_id}")
        return count
    
    # === Refund & Dispute Management ===
    
    async def process_refund(
        self,
        order_id: str,
        buyer_id: int,
        seller_id: int,
        refund_amount: Decimal,
        reason: str,
        admin_id: int,
        partial: bool = False
    ) -> Tuple[Transaction, Optional[Transaction]]:
        """עיבוד החזר (מלא או חלקי)"""
        
        # החזר לקונה
        buyer_wallet = await self.get_or_create_wallet(buyer_id)
        buyer_refund = await self.create_transaction(
            wallet=buyer_wallet,
            transaction_type=TransactionType.REFUND,
            amount=refund_amount,
            description=f"החזר {'חלקי' if partial else 'מלא'}: {reason}",
            reference_type="order",
            reference_id=order_id,
            admin_id=admin_id
        )
        
        # אם זה החזר מלא, צריך לשחרר גם את ה-hold מהמוכר
        seller_refund = None
        if not partial:
            # חיפוש hold של המוכר ושחרור
            seller_wallet = await self.get_or_create_wallet(seller_id)
            stmt = select(Transaction).where(
                and_(
                    Transaction.wallet_id == seller_wallet.id,
                    Transaction.type == TransactionType.HOLD_LOCK,
                    Transaction.reference_type == "order",
                    Transaction.reference_id == order_id
                )
            )
            result = await self.session.execute(stmt)
            hold_transaction = result.scalar_one_or_none()
            
            if hold_transaction:
                seller_refund = await self.create_transaction(
                    wallet=seller_wallet,
                    transaction_type=TransactionType.RELEASE,
                    amount=hold_transaction.amount,
                    description=f"שחרור hold עקב החזר: {reason}",
                    reference_type="order",
                    reference_id=order_id,
                    admin_id=admin_id
                )
        
        logger.info(f"Refund processed: order={order_id}, amount={refund_amount}₪, partial={partial}")
        return buyer_refund, seller_refund
    
    # === Admin Functions ===
    
    async def admin_add_balance(
        self,
        user_id: int,
        amount: Decimal,
        reason: str,
        admin_id: int
    ) -> Transaction:
        """הוספת יתרה על ידי אדמין"""
        wallet = await self.get_or_create_wallet(user_id)
        
        transaction = await self.create_transaction(
            wallet=wallet,
            transaction_type=TransactionType.SYSTEM_ADJUSTMENT,
            amount=amount,
            description=f"הוספת יתרה (אדמין): {reason}",
            reference_type="admin_adjustment",
            reference_id=str(admin_id),
            admin_id=admin_id
        )
        
        logger.info(f"Admin added balance: {amount}₪ to user {user_id} by admin {admin_id}")
        return transaction
    
    async def get_user_transaction_history(
        self,
        user_id: int,
        limit: int = 50,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        """קבלת היסטוריית תנועות משתמש"""
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        
        if transaction_type:
            stmt = stmt.where(Transaction.type == transaction_type)
        
        stmt = stmt.order_by(Transaction.created_at.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    # === Scheduled Tasks Helpers ===
    
    async def get_expired_fund_locks(self) -> List[FundLock]:
        """קבלת נעילות כספים שפגו"""
        now = datetime.now(timezone.utc)
        stmt = select(FundLock).where(
            and_(
                FundLock.is_active == True,
                FundLock.expires_at.isnot(None),
                FundLock.expires_at < now
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def cleanup_expired_locks(self) -> int:
        """ניקוי נעילות שפגו"""
        expired_locks = await self.get_expired_fund_locks()
        count = 0
        
        for lock in expired_locks:
            await self.release_fund_lock(lock.id)
            count += 1
        
        logger.info(f"Cleaned up {count} expired fund locks")
        return count
    
    async def get_orders_ready_for_release(self) -> List[str]:
        """קבלת הזמנות שמוכנות לשחרור hold"""
        now = datetime.now(timezone.utc)
        stmt = select(Order.id).where(
            and_(
                Order.status == OrderStatus.DELIVERED,
                Order.seller_hold_until.isnot(None),
                Order.seller_hold_until <= now,
                Order.buyer_confirmed_at.is_(None)  # לא אושר מוקדם
            )
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]
    
    # === Statistics & Analytics ===
    
    async def get_wallet_stats(self, user_id: int) -> Dict:
        """סטטיסטיקות ארנק משתמש"""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return {}
        
        # סה"כ הכנסות ויציאות
        stmt_income = select(Transaction).where(
            and_(
                Transaction.wallet_id == wallet.id,
                Transaction.type.in_([
                    TransactionType.DEPOSIT,
                    TransactionType.SALE_CREDIT,
                    TransactionType.REFUND,
                    TransactionType.HOLD_RELEASE
                ])
            )
        )
        
        stmt_expenses = select(Transaction).where(
            and_(
                Transaction.wallet_id == wallet.id,
                Transaction.type.in_([
                    TransactionType.PURCHASE_DEBIT,
                    TransactionType.WITHDRAWAL,
                    TransactionType.FEE_DEBIT
                ])
            )
        )
        
        income_result = await self.session.execute(stmt_income)
        expense_result = await self.session.execute(stmt_expenses)
        
        total_income = sum(t.amount for t in income_result.scalars())
        total_expenses = sum(t.amount for t in expense_result.scalars())
        
        return {
            "current_balance": wallet.total_balance,
            "available_balance": wallet.available_balance,
            "locked_balance": wallet.locked_balance,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_balance": total_income - total_expenses
        }


# === Factory Function ===

def get_wallet_service(session: AsyncSession) -> WalletService:
    """Factory function ליצירת WalletService"""
    return WalletService(session)


# TODO: Advanced Features
"""
עתיד - תכונות מתקדמות:
- Multi-currency support
- Crypto payments integration
- Payment method management (credit cards, bank transfers)
- Automatic tax calculation
- Loyalty points system
- Referral bonuses
- Subscription billing
- Risk management & fraud detection
"""
