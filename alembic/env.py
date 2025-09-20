from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from dotenv import load_dotenv

# טוען משתני סביבה מקובץ .env אם קיים (בטעינה בטוחה)
env_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(env_path):
    try:
        load_dotenv(env_path)
    except Exception:
        # התעלמות משגיאות קריאה של dotenv בסביבות לא סטנדרטיות
        pass

# זה אובייקט הקונפיג של Alembic
config = context.config


def _coerce_sync_db_url(url: str | None) -> str | None:
    if not url:
        return None
    # המרות נוחות לנהג סינכרוני
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # המרה מ-asyncpg ל-psycopg (סינכרוני)
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql+psycopg://" + url[len("postgresql+asyncpg://"):]
    # אם חסר נהג מפורש, נעדיף psycopg (psycopg3)
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


# קובע את sqlalchemy.url מתוך משתנה הסביבה DATABASE_URL (ללא תלות באפליקציה)
db_url = _coerce_sync_db_url(os.getenv("DATABASE_URL"))
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# לוגים
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# אין צורך ב-target_metadata למיגרציות ידניות (op.execute)
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
    else:
        # מצב offline ללא URL: מגדירים דיאלקט בלבד
        context.configure(
            url=None,
            target_metadata=target_metadata,
            dialect_name="postgresql",
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL is not set for online migrations")
    engine = create_engine(url)

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

