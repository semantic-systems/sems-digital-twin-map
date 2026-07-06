"""
Sets dummy DB_* env vars before any `app.*` module is imported, so importing
app.services.report_service (and the app.db module it pulls in) doesn't raise
a pydantic-settings ValidationError. No real database connection is made —
these tests only exercise pure functions and in-memory model instances.
create_engine()/sessionmaker() are lazy in SQLAlchemy, so nothing here actually
touches a socket.
"""
import os

os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
