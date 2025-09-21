import os
import asyncio
from typing import AsyncGenerator

import pytest
@pytest.fixture(scope="session")
def event_loop():
    """
    יצירת event loop גלובלי לסשן הבדיקות כדי לתמוך ב-fixtures אסינכרוניים.
    """
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


# קביעת ערכי ברירת מחדל למשתני סביבה הנדרשים כדי שטעינת ההגדרות לא תיכשל
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault(
    "DATABASE_URL",
    # כתובת DB דיפולטיבית לסביבת טסטים; מתואמת עם ה-workflow
    "postgresql+asyncpg://user:pass@localhost:5432/testdb",
)


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    """
    מריץ Alembic upgrade head לפני הבדיקות, אם מוגדר DATABASE_URL.
    אם אין מסד נתונים זמין, נטמיע דילוג על בדיקות אינטגרציה בהמשך דרך ה-fixtures.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # אין DB; בדיקות אינטגרציה ידלגו באמצעות ה-async_session fixture
        return

    try:
        from alembic.config import Config
        from alembic import command

        # שימוש בקובץ הקונפיג הקיים בשורש הפרויקט
        alembic_cfg = Config(os.path.join(os.getcwd(), "alembic.ini"))
        # מוודאים שהנתיב לתסריטי Alembic מוגדר נכון
        alembic_cfg.set_main_option("script_location", os.path.join(os.getcwd(), "alembic"))

        # הרצת מיגרציות עד ל-head
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        # אם המיגרציות נכשלו (למשל DB לא נגיש), לא נפיל את כל הסשן. בדיקות אינטגרציה
        # שדורשות DB ידלגו מאוחר יותר דרך ה-async_session fixture.
        return


@pytest.fixture()
async def async_session(event_loop) -> AsyncGenerator:
    """
    מספק AsyncSession נגד מסד נתונים אמיתי. אם DATABASE_URL לא מוגדר או החיבור נכשל,
    נדלג על טסטים שמשתמשים ב-fixture זה.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("Skipping integration tests: DATABASE_URL is not set")

    try:
        from app.database import db_manager

        # אתחול מנהל המסד אם טרם אותחל
        if not db_manager._initialized:
            await db_manager.initialize()

        # פתיחת session אסינכרוני לשימוש בבדיקות
        async with db_manager.get_session() as session:
            yield session
        # סגירת חיבורים בסיום כדי למנוע Event loop is closed
        await db_manager.close()

    except Exception as exc:
        pytest.skip(f"Skipping integration tests: cannot connect to database ({exc})")

