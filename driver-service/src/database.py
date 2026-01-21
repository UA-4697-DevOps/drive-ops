import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Try to read DATABASE_URL from environment
raw_url = os.environ.get("DATABASE_URL")

if not raw_url:
    # Build DATABASE_URL from individual env vars (docker-compose passes these)
    db_user = os.environ.get("DB_USER", "postgres")
    db_password = os.environ.get("DB_PASSWORD", "postgres")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DRIVER_DB_NAME", "driver_db")

    raw_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    print(f"✅ Built DATABASE_URL from env vars: postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}")
else:
    print(f"✅ Using DATABASE_URL from environment")

# Для асинхронної роботи SQLAlchemy потрібен драйвер +asyncpg
DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://")

try:
    engine = create_async_engine(DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
except Exception as e:
    print(f"❌ Помилка ініціалізації бази даних: {e}")
    raise

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session