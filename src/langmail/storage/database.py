"""PersonalMail AI — Database connection and session management.

Provides a clean connection abstraction and repository foundation.
"""

import sqlite3
from contextlib import contextmanager
from typing import Generator

from langmail.config import DB_FILE
from langmail.storage.schema import run_migrations


def get_connection(db_path=None) -> sqlite3.Connection:
    """Return a SQLite connection with row factory configured."""
    target_path = db_path or DB_FILE
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    return conn


@contextmanager
def db_session(db_path=None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
