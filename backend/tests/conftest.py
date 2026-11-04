import os
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set required JWT secret for test session if not set (min 32 bytes)
os.environ.setdefault(
    "RADAR_JWT_SECRET", "test-secret-key-32-bytes-minimum-length-for-hmac-sha256"
)
os.environ.setdefault("RADAR_ALLOWED_ORIGINS", "http://localhost:3000,http://test")

from app.db.connection import Base, get_db
from app.forecasting import close_forecast_channel
from app.main import create_app


@pytest.fixture(autouse=True)
def mail_outbox(monkeypatch):
    messages = {}
    monkeypatch.setattr(
        "app.email_verification.send_verification_email",
        lambda email, code: messages.__setitem__(email, code),
    )
    return messages


@pytest.fixture
def register_user(mail_outbox):
    async def register(client, payload):
        response = await client.post("/api/auth/register", json=payload)
        assert response.status_code == 201
        email = response.json()["email"]
        verified = await client.post(
            "/api/auth/verify-email", json={"email": email, "code": mail_outbox[email]}
        )
        assert verified.status_code == 200
        return response

    return register


def get_test_db_url() -> str | None:
    url = os.environ.get("RADAR_TEST_DATABASE_URL")
    if not url:
        url = os.environ.get("RADAR_DATABASE_URL")
    if not url:
        return None

    parsed = urlsplit(url)
    db_name = parsed.path.lstrip("/")
    # Require strictly that the database name itself ends with _test or -test
    if not db_name.endswith(("_test", "-test")):
        return None

    return url


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = get_test_db_url()
    if not url:
        pytest.skip(
            "Integration tests skipped: database URL with a database name strictly ending in '_test' or '-test' "
            "is required to prevent modifying non-test databases."
        )
    return url


@pytest.fixture(scope="session", autouse=True)
def setup_test_schema(test_db_url: str):
    import asyncio

    async def _setup():
        engine = create_async_engine(test_db_url, poolclass=pool.NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())
    yield

    async def _teardown():
        engine = create_async_engine(test_db_url, poolclass=pool.NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())


@pytest_asyncio.fixture
async def test_engine(test_db_url: str):
    engine = create_async_engine(test_db_url, poolclass=pool.NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(test_engine):
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield
    await close_forecast_channel()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
