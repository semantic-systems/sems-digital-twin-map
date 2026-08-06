# sems-digital-twin-map

An interactive situational map of Hamburg that combines open geodata from the
[Urban Data Hub](https://api.hamburg.de/datasets/v1/) with near-real-time
social media reports (Mastodon, Bluesky, Reddit, RSS news) ingested from the
RescueMate Knowledge Graph.

![Screenshot of Map](/docs/img/screenshot_map.png)

## Features
- **Geodata layers** — toggleable map layers built from OGC API Features
  datasets (e.g. schools, traffic infrastructure), configured in
  [`api_config.json`](api_config.json).
- **Live report feed** — social media posts and news headlines are polled
  from a RescueMate SPARQL endpoint, geolocated, and shown as pins with a
  filterable sidebar list (platform, relevance, event type, time range,
  free-text search, drawn spatial area).
- **Report triage** — mark reports as seen, flag an author across all their
  posts, and view per-user state (each logged-in user has their own
  seen/flagged/hidden state).
- **Admin & auth** — cookie-session login, user management, and a demo mode
  that serves seeded data instead of live posts.
- **Retention** — reports older than `REPORT_RETENTION_DAYS` (default 7) are
  purged automatically.

## Architecture
| Layer | Tech |
|---|---|
| Frontend | React + TypeScript (Vite), react-leaflet, Zustand, Tailwind CSS |
| Backend | FastAPI (Python), SQLAlchemy |
| Database | PostgreSQL + PostGIS |
| Ingestion | `server_reports` (RescueMate SPARQL polling worker) |

The backend and frontend are the current, actively developed application.
`src/` holds the shared SQLAlchemy models/DB layer used by both the backend
and the ingestion workers, plus the original Dash prototype (reference only,
no longer deployed). See [docs/layout.md](/docs/layout.md) for the full code
layout.

## Quick start (Docker)
1. Clone the repository: `git clone https://github.com/semantic-systems/sems-digital-twin-map`
2. Copy `example.env` to `.env` and fill in the values (DB credentials,
   RescueMate SPARQL endpoint + Keycloak credentials, admin bootstrap login).
3. Launch everything: `docker compose up -d --build`

| Service | URL | Purpose |
|---|---|---|
| frontend | http://localhost:8050/ | React map UI |
| backend | http://localhost:8052/ | FastAPI REST API (Swagger UI at `/docs`) |
| postgis | localhost:5432 (dev only) | PostgreSQL + PostGIS |
| pgadmin | http://localhost:8051/ | DB admin UI |

See [docs/setup.md](/docs/setup.md) and [docs/servers.md](/docs/servers.md)
for details on each service.

## Local development
For faster iteration, run only the database in Docker and the app locally:

```bash
./start_dev.sh                 # starts postgis + pgadmin (docker-compose.dev.yaml)
cd backend && uvicorn app.main:app --reload --port 8052
cd frontend && npm run dev     # http://localhost:5173, proxies /api to :8052
```

### Tests
```bash
# backend (pytest)
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
python -m pytest backend/tests

# frontend (vitest)
cd frontend && npm test
```

## Project structure
```
backend/    FastAPI app: routers/, services/, schemas/, config.py, db.py
frontend/   React app: src/components/, src/store/, src/api/, src/hooks/
src/        Shared DB models (data/), ingestion workers (server_reports.py,
            server_nina.py), legacy Dash prototype (app/, reference only)
docker/     Dockerfiles + nginx config for the ingestion workers
docs/       In-depth documentation (see below)
```

## Documentation
- [docs/setup.md](/docs/setup.md) — full setup & configuration walkthrough
- [docs/servers.md](/docs/servers.md) — what each container/service does
- [docs/datamodel.md](/docs/datamodel.md) — database schema (SQLAlchemy models)
- [docs/datasources.md](/docs/datasources.md) — configuring OGC API Features geodata sources
- [docs/layout.md](/docs/layout.md) — frontend/backend code layout
