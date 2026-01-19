import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

# Вказуємо шлях до .env явно, якщо він на рівень вище
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    # Якщо DATABASE_URL не знайдено, використовуємо дефолтний для локальної розробки
    print("⚠️ DATABASE_URL не знайдено в .env, використовую дефолтний шлях")
    raw_url = "postgresql://postgres:postgres@localhost:5432/driver_db"

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