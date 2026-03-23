from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Walk up the directory tree to find the src/ package (works both locally and in Docker)
_search = os.path.abspath(os.path.dirname(__file__))
_SRC_PATH: str = ""
for _ in range(6):
    _candidate = os.path.join(_search, "src")
    if os.path.isdir(_candidate):
        _SRC_PATH = _candidate
        break
    _parent = os.path.dirname(_search)
    if _parent == _search:
        break
    _search = _parent
if _SRC_PATH and _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# Now the existing models are importable as  data.model
from data.model import (  # noqa: E402  (import not at top of file)
    Base,
    Colormap,
    Feature,
    FeatureSet,
    Layer,
    Report,
    Scenario,
    Style,
    UserReportState,
)

from .config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------
_engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

_SessionFactory: sessionmaker[Session] = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-manager session (for use outside of FastAPI request scope)."""
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it on exit."""
    session: Session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()


__all__ = [
    "get_db",
    "get_session",
    # re-exported models so other modules can import from a single place
    "Base",
    "Colormap",
    "Feature",
    "FeatureSet",
    "Layer",
    "Report",
    "Scenario",
    "Style",
    "UserReportState",
]
