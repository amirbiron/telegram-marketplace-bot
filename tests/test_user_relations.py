import pytest
import random
from app.models.user import User, Wallet, SellerProfile


@pytest.mark.asyncio
async def test_user_wallet_and_seller(async_session):
    # יצירת משתמש חדש
    user = User(
        telegram_user_id=random.randint(1_000_000_000, 10_000_000_000),
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_session.add(user)
    await async_session.flush()
    assert user.id is not None

    # יצירת ארנק דרך user_id (נדרש ע"י הדאטהקלאס)
    wallet = Wallet(user_id=user.id, transactions=[], fund_locks=[])
    async_session.add(wallet)

    # יצירת פרופיל מוכר - שומר גם user וגם user_id
    seller = SellerProfile(user=user, user_id=user.id, business_name="Test Biz")
    async_session.add(seller)

    # flush למסד
    await async_session.flush()

    # בדיקות
    assert wallet.id is not None
    assert wallet.user_id == user.id
    assert seller.id is not None
    assert seller.user_id == user.id

