from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import demo, geo, reports, user
from .routers.layers import router as layers_router
from .routers.layers import scenarios_router


def _init_db() -> None:
    """Run DB initialisation in a background thread so startup is non-blocking."""
    try:
        from data.build import build_if_uninitialized  # noqa: PLC0415
        build_if_uninitialized()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] DB init failed: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    threading.Thread(target=_init_db, daemon=True).start()
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
