import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    print("❌ DATABASE_URL must be set", file=sys.stderr)
    sys.exit(1)

# SQLAlchemy async requires the +asyncpg driver prefix
DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

try:
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
except Exception as e:
    print(f"❌ Database initialization error: {e}", file=sys.stderr)
    raise


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
