import pytest

from app.models.user import User, UserRole


def test_create_user_minimal_buyer() -> None:
    user = User(
        id=1,
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
        id=2,
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
