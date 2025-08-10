from os import getenv

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

POSTGRES_DB = getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = getenv("POSTGRES_HOST", "db")
DATABASE_URL: str = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/{POSTGRES_DB}"
engine = create_async_engine(DATABASE_URL, echo=False)


async def get_db_session():
    async with AsyncSession(engine) as session:
        yield session
