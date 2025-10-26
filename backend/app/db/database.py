from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite+aiosqlite:////app/data/games.db"

engine = create_async_engine(DATABASE_URL, echo=True)

Base = declarative_base()

async_session = sessionmaker (
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with async_session() as session:
        yield session
