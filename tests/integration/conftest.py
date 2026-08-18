import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss")
    )
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                try:
                    yield session
                finally:
                    await session.rollback()
            await outer_transaction.rollback()
    finally:
        await engine.dispose()
