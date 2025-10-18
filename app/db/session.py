from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

DATABASE_URL_ASYNC = settings.DATABASE_URL.replace('psycopg2', 'asyncpg')
engine = create_async_engine(DATABASE_URL_ASYNC, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session