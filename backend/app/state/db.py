"""SQLite state engine.

SQLModel + SQLAlchemy engine, created lazily so test code can override the path.
The DB file lives wherever STATE_DB_PATH points (default ./data/state.db).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import Settings


def _ensure_parent(db_path: str) -> None:
    parent = Path(db_path).resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def make_engine(settings: Settings):
    _ensure_parent(settings.state_db_path)
    url = f"sqlite:///{settings.state_db_path}"
    engine = create_engine(
        url,
        echo=False,
        # timeout: SQLite waits up to 30s for a busy lock to release before erroring.
        # Default is 5s, which is too short when the schema refresher and a chat
        # write race for the lock on app startup.
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    # WAL mode lets readers and one writer run concurrently without blocking
    # each other. Critical for our threading model (schema refresh task + chat
    # endpoint + schema browser all sharing one DB).
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        conn.commit()
    return engine


def init_schema(engine) -> None:
    # Importing models registers them with SQLModel.metadata
    from app.state import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def session_scope(engine) -> Iterator[Session]:
    """Generator usable as FastAPI dependency."""
    with Session(engine) as session:
        yield session
