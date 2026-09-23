import os
import uuid
import asyncio
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

TEST_DB_PATH = "/tmp/myairouter_test.db"
test_db_url = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["DATABASE_URL"] = test_db_url
# Test-only credentials keep application startup fail-closed without relying on
# any developer machine secrets.
os.environ["ROUTER_MASTER_KEY"] = Fernet.generate_key().decode()
os.environ["JWT_SECRET"] = "test-jwt-secret-" + uuid.uuid4().hex
os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
os.environ["FINGERPRINT_SALT"] = "test-fingerprint-salt-" + uuid.uuid4().hex

from app.core.config import settings
settings.DATABASE_URL = test_db_url
settings.COOKIE_SECURE = False

import app.core.database as db_module
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event

db_module.engine = create_async_engine(
    test_db_url,
    connect_args={"check_same_thread": False},
    future=True,
)
@event.listens_for(db_module.engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

db_module.AsyncSessionLocal = async_sessionmaker(
    bind=db_module.engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

from app.core.database import engine, Base
import app.models.entities
from app.services.auth_service import AuthService

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with db_module.AsyncSessionLocal() as session:
            await AuthService.init_admin_user(session)
    asyncio.run(init())
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest.fixture(autouse=True)
def clean_test_env():
    # Set unique salt or test configuration
    os.environ["FINGERPRINT_SALT"] = "test-salt-" + uuid.uuid4().hex
    yield
