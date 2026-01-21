import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# 1. Налаштування шляхів пошуку модулів
# Додаємо корінь проекту (driver-service) до sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 2. Завантаження змінних оточення з .env
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

# 3. ІМПОРТ МОДЕЛЕЙ (тепер через звичайний імпорт)
try:
    from src.driver_models import Base
except ImportError as e:
    print(f"\n[!] Помилка імпорту: Переконайся, що файл названо src/driver_models.py")
    print(f"[!] Текст помилки: {e}")
    sys.exit(1)

target_metadata = Base.metadata

# Стандартний об'єкт конфігурації Alembic
config = context.config

# Налаштування логування
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_url():
    """Отримує URL бази даних з оточення."""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Запасний варіант, якщо DATABASE_URL не задано
        user = os.getenv("DB_USER", "postgres")
        pw = os.getenv("DB_PASSWORD", "postgres")
        db = os.getenv("DRIVER_DB_NAME", "driver_db")
        host = os.getenv("DB_HOST", "localhost")
        url = f"postgresql://{user}:{pw}@{host}:5432/{db}"
    return url


def run_migrations_offline() -> None:
    """Запуск міграцій в 'offline' режимі (генерація SQL файлів)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск міграцій в 'online' режимі (безпосередньо в базу)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url(),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()