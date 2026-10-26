import os

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Point the app at the TEST database before anything imports the app.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel_test",
)

from app.api.deps import get_current_user  # noqa: E402, F401
from app.core.redis import redis  # noqa: E402
from app.core.security import generate_api_key, hash_api_key  # noqa: E402
from app.db.base import get_session  # noqa: E402
from app.db.models import Base, User  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_DB_URL = os.environ["DATABASE_URL"]

# Safety net: never run tests against anything that is not a test database,
# because the tests wipe every table.
assert "test" in TEST_DB_URL, f"Refusing to run tests against {TEST_DB_URL}"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def _clear_redis() -> None:
    for pattern in ("ratelimit:*", "stats:*"):
        async for key in redis.scan_iter(pattern):
            await redis.delete(key)


@pytest_asyncio.fixture(autouse=True)
async def clean_state(engine):
    """Start every test from a known, empty state."""
    await _clear_redis()
    yield
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def user_and_key(session_factory) -> tuple[User, str]:
    key = generate_api_key()
    async with session_factory() as s:
        user = User(email="test@example.com", api_key_hash=hash_api_key(key))
        s.add(user)
        await s.commit()
        await s.refresh(user)
    return user, key


@pytest_asyncio.fixture
async def client(engine, session_factory):
    app = create_app()

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
