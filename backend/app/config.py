from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database — required
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # Infrastructure
    IN_DOCKER: bool = False

    # Feature flags
    DEMO_MODE: bool = False

    # Retention: reports older than this many days are deleted by the background
    # purge (see data/retention.py, main.py::_purge_loop). 0 or negative disables
    # the purge and lets the table grow without bound.
    REPORT_RETENTION_DAYS: int = 7

    # Auth: set True in production (HTTPS) so the session cookie is only sent over
    # TLS. Left False for local http dev.
    COOKIE_SECURE: bool = False

    # SameSite policy of the session cookie. Must be "none" wherever the app is
    # embedded as a cross-site iframe (e.g. the RescueMate Lagebild on
    # rescue-mate-lagebild.web.hcds.uni-hamburg.de framing map.skynet.coypu.org):
    # SameSite is evaluated against the TOP-LEVEL site, not the frame's own origin,
    # so with "lax" the browser silently refuses to store the cookie set by a
    # successful login and every following request comes back 401.
    # "none" implies Secure + Partitioned — see auth._cookie_kwargs.
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Optional bootstrap admin, created on startup if the username doesn't exist
    # yet (see auth.ensure_default_admin). Lets docker-compose provision a first
    # admin so you can log in without shell access. Only creates — never resets an
    # existing account's password — so changing it in-app survives restarts.
    DEFAULT_ADMIN_USER: str = ""
    DEFAULT_ADMIN_PASSWORD: str = ""

    # External services
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Extra origins allowed to make state-changing (POST/PUT/DELETE) requests, on
    # top of CORS_ORIGINS and the app's own host — see csrf.origin_check_middleware.
    # Normally empty: an embedded frame serves the app's own bundle, so its calls
    # are same-origin. Only needed if another site must call this API directly.
    TRUSTED_ORIGINS: list[str] = []

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def normalize_samesite(cls, v: object) -> object:
        # "None"/"NONE" in .env is the obvious way to write this and would
        # otherwise fail validation at startup, taking the whole API down.
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("CORS_ORIGINS", "TRUSTED_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    @property
    def db_host(self) -> str:
        return "postgis" if self.IN_DOCKER else "localhost"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.db_host}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
