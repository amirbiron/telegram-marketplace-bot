import pytest
from decimal import Decimal

from app.models.user import User, UserRole, Wallet, SellerProfile


def test_create_user_minimal_buyer() -> None:
    user = User(
        telegram_user_id=111111111,
        username="testbuyer",
        first_name="Test",
        last_name="Buyer",
    )

    assert user.telegram_user_id == 111111111
    assert user.first_name == "Test"
    assert user.username == "testbuyer"

    # שדות אופציונליים/קשרים לא נדרשים ב-__init__
    assert user.phone is None
    assert user.email is None
    assert user.last_activity_at is not None
    assert user.wallet is None
    assert len(user.transactions) == 0
    assert len(user.fund_locks) == 0


def test_create_user_minimal_seller() -> None:
    user = User(
        telegram_user_id=222222222,
        username="testseller",
        first_name="Test",
        last_name="Seller",
        role=UserRole.SELLER,
    )

    assert user.telegram_user_id == 222222222
    assert user.role == UserRole.SELLER
    assert user.wallet is None
    assert len(user.transactions) == 0
    assert len(user.fund_locks) == 0


@pytest.mark.asyncio
async def test_user_gets_id_after_flush(async_session):
    user = User(
        telegram_user_id=1234567890,
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_session.add(user)
    await async_session.flush()
    assert user.id is not None


@pytest.mark.asyncio
async def test_wallet_creation(async_session):
    user = User(
        telegram_user_id=1234567891,
        username="walletuser",
        first_name="Wallet",
        last_name="User",
    )
    async_session.add(user)
    await async_session.flush()

    assert user.id is not None
    wallet = Wallet(user=user, transactions=[], fund_locks=[])
    async_session.add(wallet)
    await async_session.flush()
    assert wallet.id is not None
    assert wallet.user_id == user.id


@pytest.mark.asyncio
async def test_seller_profile_creation(async_session):
    user = User(
        telegram_user_id=1234567892,
        username="selleruser",
        first_name="Seller",
        last_name="User",
    )
    async_session.add(user)
    await async_session.flush()

    assert user.id is not None
    seller = SellerProfile(
        user=user,
        business_name="Test Biz",
        description="",
        verification_documents=[],
        average_rating=Decimal("0.00"),
    )
    async_session.add(seller)
    await async_session.flush()
    assert seller.id is not None
    assert seller.user_id == user.id
