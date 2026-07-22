"""
Dumps the FastAPI app's OpenAPI schema to backend/openapi.json — the single
source of truth the frontend generates its request/response types from
(see frontend/package.json's "gen:types" script), instead of hand-maintaining
matching TypeScript interfaces that can silently drift from what the backend
actually accepts/returns (e.g. the `only_new` query param existing on three
endpoints but missing from one hand-written frontend params type earlier this
session).

Importing app.main only defines routes/schemas — it does NOT start the app
(FastAPI's lifespan / _init_db, which needs a live Postgres, only runs when the
app is actually served), so this needs no database connection. Run from
backend/ with: python scripts/export_openapi.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Dummy DB_* env vars so Settings() can be constructed (see tests/conftest.py
# for the same rationale) — no real connection is made.
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "placeholder")
os.environ.setdefault("DB_PASSWORD", "placeholder")
os.environ.setdefault("DB_NAME", "placeholder")

from app.main import app  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openapi.json")


def main() -> None:
    schema = app.openapi()
    with open(OUT_PATH, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    print(f"Wrote {OUT_PATH} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
