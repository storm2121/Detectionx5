"""Engine, sessions and migrations.

The same Alembic migrations create the schema on PostgreSQL (Compose) and on SQLite (tests
and single-machine use), so the tests exercise the production schema. SQLite gets foreign
keys switched on per connection, which it does not do by default.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def ensure_sqlite_dir(url: str) -> None:
    """SQLite creates the database file but not its folder; create the folder first."""
    if url.startswith("sqlite") and ":///" in url and not url.endswith(":memory:"):
        Path(url.split(":///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        ensure_sqlite_dir(url)
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection: Any, _: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def migrate(url: str) -> None:
    """Upgrade the database at ``url`` to the latest revision."""
    ensure_sqlite_dir(url)
    command.upgrade(alembic_config(url), "head")


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = make_engine(url)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


__all__ = ["Database", "alembic_config", "ensure_sqlite_dir", "make_engine", "migrate"]
