from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import demo, geo, reports, user
from .routers.layers import router as layers_router
from .routers.layers import scenarios_router

app = FastAPI(
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
