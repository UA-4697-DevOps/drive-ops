import os
import sys
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    print("❌ DATABASE_URL must be set", file=sys.stderr)
    sys.exit(1)

# SQLAlchemy async requires the postgresql+asyncpg:// driver prefix.
# Normalise both "postgresql://" and "postgres://" (Heroku-style) variants,
# and skip substitution if the driver is already present.
if "+asyncpg" in raw_url:
    DATABASE_URL = raw_url
elif raw_url.startswith("postgresql://"):
    DATABASE_URL = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]
elif raw_url.startswith("postgres://"):
    DATABASE_URL = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
else:
    print(f"❌ DATABASE_URL has an unsupported scheme: {raw_url.split('://')[0]}://", file=sys.stderr)
    sys.exit(1)

# asyncpg does not accept the psycopg2-style 'sslmode' query parameter.
# Strip it from the URL and map it to a connect_args ssl flag instead.
_parsed = urlparse(DATABASE_URL)
_qs = parse_qs(_parsed.query, keep_blank_values=True)
_sslmode = _qs.pop("sslmode", [None])[0]
_clean_url = urlunparse(_parsed._replace(query=urlencode({k: v[0] for k, v in _qs.items()})))
DATABASE_URL = _clean_url

_connect_args = {}
if _sslmode and _sslmode != "disable":
    _connect_args["ssl"] = True

try:
    engine = create_async_engine(DATABASE_URL, echo=True, connect_args=_connect_args)
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
