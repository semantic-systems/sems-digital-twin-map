# Layout

The frontend is a React (Vite/TypeScript) application located in `frontend/`. It communicates with the FastAPI backend at `http://localhost:8052/` via a REST API.

## Frontend structure (`frontend/src/`)
- `main.tsx` — entry point, mounts the React app
- `App.tsx` — root component, handles top-level layout and layer auto-activation on fresh deployments
- `components/` — UI components (map, sidebar, filterbar, shared widgets)
- `hooks/` — custom React hooks
- `store/` — global state management
- `api/` — typed API client functions for communicating with the backend
- `i18n/` — internationalisation strings
- `types.ts` / `constants.ts` — shared TypeScript types and constants

## Backend structure (`backend/app/`)
- `main.py` — FastAPI app entry point, lifespan DB init, CORS, router registration
- `routers/` — route handlers: `reports.py`, `layers.py`, `user.py`, `geo.py`, `demo.py`
- `schemas/` — Pydantic request/response schemas
- `services/` — business logic
- `db.py` — SQLAlchemy engine and session setup
- `config.py` — settings loaded from environment variables
