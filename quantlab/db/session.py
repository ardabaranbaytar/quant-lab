"""Engine/session management. Connection settings come from the environment.

Resolution order:
1. ``DATABASE_URL`` (any SQLAlchemy URL)
2. ``MYSQL_USER`` / ``MYSQL_PASSWORD`` / ``MYSQL_HOST`` / ``MYSQL_PORT`` / ``MYSQL_DATABASE``
3. local SQLite file ``quantlab.db``
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def database_url() -> str | URL:
    if url := os.getenv("DATABASE_URL"):
        return url
    if user := os.getenv("MYSQL_USER"):
        return URL.create(
            "mysql+pymysql",
            username=user,
            password=os.getenv("MYSQL_PASSWORD"),
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "quantlab"),
            query={"charset": "utf8mb4"},
        )
    return "sqlite:///quantlab.db"


@lru_cache
def get_engine(url: str | URL | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True, future=True)


def create_database_if_missing(url: URL) -> None:
    """MySQL only: ``CREATE DATABASE IF NOT EXISTS`` for the configured schema."""
    # Note: url.set(database=None) is a no-op in SQLAlchemy, so rebuild the URL.
    server_url = URL.create(
        url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        query=url.query,
    )
    server = create_engine(server_url, future=True)
    with server.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    server.dispose()


def init_db(engine: Engine | None = None) -> Engine:
    from quantlab.db.models import Base

    if engine is None:
        url = database_url()
        if isinstance(url, URL) and url.get_backend_name() == "mysql":
            create_database_if_missing(url)
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
