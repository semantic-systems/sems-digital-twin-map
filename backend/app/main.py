from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import demo, geo, reports, user
from .routers.layers import router as layers_router
from .routers.layers import scenarios_router


def _init_db() -> None:
    """
    Wait for PostgreSQL, then ensure all critical tables exist.
    Each statement runs in its own transaction so one failure never aborts the rest.
    """
    from .db import _engine  # noqa: PLC0415
    from sqlalchemy import text

    # Wait for PostgreSQL to be ready (depends_on only waits for container start)
    for attempt in range(30):
        try:
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[startup] PostgreSQL is ready.")
            break
        except Exception:  # noqa: BLE001
            print(f"[startup] Waiting for PostgreSQL... ({attempt + 1}/30)")
            time.sleep(2)
    else:
        print("[startup] PostgreSQL not ready after 60s — proceeding anyway.")

    statements = [
        "CREATE EXTENSION IF NOT EXISTS postgis",
        """CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            identifier VARCHAR,
            text TEXT,
            url VARCHAR,
            platform VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            relevance VARCHAR,
            locations JSON,
            original_locations JSON,
            author VARCHAR DEFAULT '',
            seen BOOLEAN NOT NULL DEFAULT FALSE,
            author_flagged BOOLEAN NOT NULL DEFAULT FALSE
        )""",
        """CREATE TABLE IF NOT EXISTS user_report_state (
            id SERIAL PRIMARY KEY,
            username VARCHAR NOT NULL,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            hide BOOLEAN NOT NULL DEFAULT FALSE,
            flag BOOLEAN NOT NULL DEFAULT FALSE,
            flag_author VARCHAR,
            locations JSON,
            first_seen_at TIMESTAMP,
            new BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_user_report UNIQUE (username, report_id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_urs_username ON user_report_state (username)",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS original_locations JSON",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS author VARCHAR DEFAULT ''",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS seen BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS author_flagged BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE user_report_state ADD COLUMN IF NOT EXISTS new BOOLEAN NOT NULL DEFAULT TRUE",
    ]

    for sql in statements:
        try:
            with _engine.begin() as conn:
                conn.execute(text(sql))
            print(f"[startup] OK: {sql[:70].strip()!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] SKIP: {exc!s:.100}")

    print("[startup] DB init complete.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    _init_db()  # blocks until tables exist — fast, no external calls
    yield


app = FastAPI(
    lifespan=lifespan,
    title="SEMS Digital Twin Map API",
    version="1.0.0",
    description=(
        "REST API backend for the SEMS Digital Twin Map. "
        "Serves reports, map layers, scenarios, and per-user state."
    ),
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(reports.router)
app.include_router(layers_router)
app.include_router(scenarios_router)
app.include_router(user.router)
app.include_router(geo.router)
app.include_router(demo.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/v1/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
