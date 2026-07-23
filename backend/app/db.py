from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# The shared DB layer lives in the `data` package (src/data). Preferred setup:
# install it (`pip install -e .` at the repo root — see pyproject.toml) or put
# src/ on PYTHONPATH. If neither is the case, fall back to the two known
# checkout layouts instead of the previous walk-up-until-something-matches
# search, which silently depended on directory naming and could pick up an
# unrelated src/ directory:
#   repo checkout:  <repo>/backend/app/db.py  ->  <repo>/src
#   Docker image:   /app/app/db.py            ->  /app/src   (see backend/Dockerfile)
try:
    import data.model  # noqa: F401
except ImportError:
    _here = os.path.abspath(os.path.dirname(__file__))
    _candidates = [
        os.path.normpath(os.path.join(_here, "..", "..", "src")),  # repo checkout
        os.path.normpath(os.path.join(_here, "..", "src")),        # Docker image
    ]
    for _src in _candidates:
        if os.path.isdir(os.path.join(_src, "data")):
            if _src not in sys.path:
                sys.path.insert(0, _src)
            break
    else:
        raise ImportError(
            "Cannot import the shared `data` package. Install it with "
            "`pip install -e .` from the repo root, or ensure src/ is on "
            f"PYTHONPATH. Tried: {_candidates}"
        )

from data.model import (  # noqa: E402  (import not at top of file)
    Base,
    Colormap,
    Feature,
    FeatureSet,
    Layer,
    LocationPolygon,
    Report,
    Scenario,
    Style,
    User,
    UserAdmission,
    UserReportState,
    UserSession,
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
    # Disable JIT for every connection. This is a short-query OLTP workload where
    # JIT rarely amortizes, and it's actively harmful for the drawn-area
    # (PostGIS-over-JSON) queries: Postgres wildly over-estimates their cost via the
    # json_array_elements cardinality guess and would spend 60ms–1s JIT-compiling a
    # query whose real work is a few ms (verified against the live DB).
    connect_args={"options": "-c jit=off"},
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
    "_engine",
    # re-exported models so other modules can import from a single place
    "Base",
    "Colormap",
    "Feature",
    "FeatureSet",
    "Layer",
    "LocationPolygon",
    "Report",
    "Scenario",
    "Style",
    "User",
    "UserAdmission",
    "UserReportState",
    "UserSession",
]
