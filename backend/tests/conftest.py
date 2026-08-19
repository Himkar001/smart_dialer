"""
pytest configuration and fixtures.

Uses SQLite (aiosqlite) for fast in-memory testing — no PostgreSQL needed.
SELECT FOR UPDATE is not supported by SQLite, so reserve_agent() is tested
via its None-return paths. Real concurrency guarantees are provided by
PostgreSQL in production; architecture tests verify the logic is correct.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Agent, AgentState, Borrower, Call, CallState, Campaign, CampaignMode, ProviderType

# Use in-memory SQLite for fast, dependency-free unit tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a fresh in-memory SQLite engine for each test function."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async DB session for each test."""
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def campaign(db: AsyncSession) -> Campaign:
    """Create and persist a test campaign."""
    c = Campaign(
        name="Test Campaign",
        mode=CampaignMode.PROGRESSIVE,
        provider=ProviderType.PROVIDER_A,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def available_agent(db: AsyncSession, campaign: Campaign) -> Agent:
    """Create a single AVAILABLE agent assigned to the test campaign."""
    a = Agent(
        name="Test Agent",
        state=AgentState.AVAILABLE,
        campaign_id=campaign.id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@pytest_asyncio.fixture
async def borrower(db: AsyncSession, campaign: Campaign) -> Borrower:
    """Create a sample borrower for the test campaign."""
    b = Borrower(
        name="Test Borrower",
        phone="+1234567890",
        campaign_id=campaign.id,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return b


@pytest_asyncio.fixture
async def queued_call(db: AsyncSession, campaign: Campaign, borrower: Borrower) -> Call:
    """Create a QUEUED call ready for state machine tests."""
    c = Call(
        campaign_id=campaign.id,
        borrower_id=borrower.id,
        state=CallState.QUEUED,
        provider="PROVIDER_A",
        idempotency_key=str(uuid.uuid4()),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c
