import pytest
from app.models.user import User, Wallet, SellerProfile


@pytest.mark.asyncio
async def test_user_wallet_and_seller(async_session):
    # יצירת משתמש חדש
    user = User(telegram_user_id=1234567890, username="testuser")
    async_session.add(user)
    await async_session.flush()
    assert user.id is not None

    # יצירת ארנק דרך relationship
    wallet = Wallet(user=user, transactions=[], fund_locks=[])
    async_session.add(wallet)

    # יצירת פרופיל מוכר דרך relationship
    seller = SellerProfile(user=user, business_name="Test Biz")
    async_session.add(seller)

    # flush למסד
    await async_session.flush()

    # בדיקות
    assert wallet.id is not None
    assert wallet.user_id == user.id
    assert seller.id is not None
    assert seller.user_id == user.id

