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
    from .db import Base, _engine  # noqa: PLC0415
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

    Base.metadata.create_all(_engine)
    print("[startup] All ORM tables ensured.")

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
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS event_types VARCHAR[]",
        "UPDATE reports SET event_types = ARRAY[event_type]::VARCHAR[] WHERE event_types IS NULL OR event_types = '{}'",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS processing_status VARCHAR",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS geo_recognition_status VARCHAR",
        # Admission watermark (see UserAdmission model). The backfill converts the
        # legacy per-report first_seen_at admission rows into each user's watermark
        # once; ON CONFLICT keeps later startups from touching an existing value.
        """CREATE TABLE IF NOT EXISTS user_admission (
            username VARCHAR PRIMARY KEY,
            admitted_up_to_id INTEGER NOT NULL DEFAULT 0
        )""",
        """INSERT INTO user_admission (username, admitted_up_to_id)
           SELECT username, MAX(report_id) FROM user_report_state
           WHERE first_seen_at IS NOT NULL
           GROUP BY username
           ON CONFLICT (username) DO NOTHING""",
        "CREATE INDEX IF NOT EXISTS ix_reports_timestamp ON reports (timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS ix_reports_platform ON reports (platform)",
        "CREATE INDEX IF NOT EXISTS ix_reports_relevance ON reports (relevance)",
        "CREATE INDEX IF NOT EXISTS ix_reports_identifier_prefix ON reports (identifier text_pattern_ops)",
        "CREATE INDEX IF NOT EXISTS ix_reports_event_types_gin ON reports USING GIN (event_types)",
        "CREATE INDEX IF NOT EXISTS ix_urs_report_id ON user_report_state (report_id)",
        "CREATE INDEX IF NOT EXISTS ix_urs_username_first_seen ON user_report_state (username, first_seen_at) WHERE first_seen_at IS NOT NULL",
        # Deduplicated polygon storage
        """CREATE TABLE IF NOT EXISTS location_polygons (
            osm_id VARCHAR NOT NULL,
            osm_type VARCHAR NOT NULL,
            polygon JSON NOT NULL,
            PRIMARY KEY (osm_id, osm_type)
        )""",
        # Backfill unique polygons still present in locations (idempotent via ON CONFLICT)
        """INSERT INTO location_polygons (osm_id, osm_type, polygon)
           SELECT DISTINCT ON (e->>'osm_id', e->>'osm_type')
               e->>'osm_id', e->>'osm_type', e->'polygon'
           FROM reports, LATERAL json_array_elements(locations) AS e
           WHERE (e->>'osm_id') IS NOT NULL
             AND (e->>'osm_type') IS NOT NULL
             AND (e->>'polygon') IS NOT NULL
           ON CONFLICT (osm_id, osm_type) DO NOTHING""",
        # Strip polygon from locations (guard makes this idempotent)
        """UPDATE reports
           SET locations = (
               SELECT json_agg(
                   (SELECT json_object_agg(k, v) FROM json_each(e) AS x(k, v) WHERE k != 'polygon')
               )
               FROM json_array_elements(locations) AS e
           )
           WHERE locations::text LIKE '%\"polygon\"%'""",
        """UPDATE reports
           SET original_locations = (
               SELECT json_agg(
                   (SELECT json_object_agg(k, v) FROM json_each(e) AS x(k, v) WHERE k != 'polygon')
               )
               FROM json_array_elements(original_locations) AS e
           )
           WHERE original_locations::text LIKE '%\"polygon\"%'""",
        # locations_slim is now identical to locations — clear to reclaim space
        "UPDATE reports SET locations_slim = NULL WHERE locations_slim IS NOT NULL",
    ]

    for sql in statements:
        try:
            with _engine.begin() as conn:
                conn.execute(text(sql))
            print(f"[startup] OK: {sql[:70].strip()!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] SKIP: {exc!s:.100}")

    # Seed a permanent example report for the onboarding tour (idempotent — the
    # WHERE NOT EXISTS guard means this only ever inserts once). It's excluded
    # from all normal listings via the 'tour-example' identifier filter in
    # report_service.build_report_query, and fetched on demand by
    # GET /api/v1/reports/tour-example. Bound params (not the statements-list
    # string-interpolation pattern above) because the JSON payload's own ':'
    # characters would otherwise be misread as SQLAlchemy bind-param markers.
    import json  # noqa: PLC0415

    try:
        with _engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO reports (identifier, text, url, platform, timestamp, event_type, event_types, relevance, locations, original_locations, author, seen, author_flagged)
                    SELECT 'tour-example', :report_text, '#', 'twitter', NOW(), :event_type, ARRAY[:event_type]::VARCHAR[], 'high', CAST(:locations AS JSON), CAST(:locations AS JSON), :author, FALSE, FALSE
                    WHERE NOT EXISTS (SELECT 1 FROM reports WHERE identifier = 'tour-example')
                    """
                ),
                {
                    "report_text": "🚨 Wasserrohrbruch in der Innenstadt – Straße gesperrt, Anwohner suchen Hilfe.",
                    "event_type": "Infrastruktur-Schäden",
                    "author": "beispiel_nutzer",
                    "locations": json.dumps([
                        {"name": "Hamburg", "display_name": "Hamburg, Deutschland", "lat": 53.5438, "lon": 9.9857},
                        {"name": "Berlin", "display_name": "Berlin, Deutschland", "lat": 52.52, "lon": 13.405},
                    ]),
                },
            )
        print("[startup] OK: seeded tour-example report")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] SKIP: tour-example seed: {exc!s:.100}")

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
