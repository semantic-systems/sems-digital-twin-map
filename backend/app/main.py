from __future__ import annotations

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
    Enable PostGIS, create all tables (if missing), run column migrations.
    Safe: never drops data. Blocks startup so tables exist before first request.
    """
    from .db import Base, _engine  # noqa: PLC0415
    from sqlalchemy import text

    # Enable PostGIS — required for geometry columns; safe to call repeatedly
    with _engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    print("[startup] PostGIS extension ensured.")

    Base.metadata.create_all(_engine)
    print("[startup] Tables ensured.")

    try:
        from data.build import migrate_columns  # noqa: PLC0415
        migrate_columns()
        print("[startup] Migrations done.")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] migrate_columns failed (non-fatal): {exc}")


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
