import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    webhook_secret: str | None
    database_url: str
    log_level: str


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip()
    return v


def get_settings() -> Settings:
    webhook_secret = _env("WEBHOOK_SECRET")
    # DATABASE_URL must point to /data/app.db in container via volume
    database_url = _env("DATABASE_URL", "sqlite:////data/app.db") or "sqlite:////data/app.db"
    log_level = (_env("LOG_LEVEL", "INFO") or "INFO").upper()
    if log_level not in {"INFO", "DEBUG"}:
        log_level = "INFO"

    # Treat empty secret as missing
    if webhook_secret is not None and webhook_secret == "":
        webhook_secret = None

    return Settings(
        webhook_secret=webhook_secret,
        database_url=database_url,
        log_level=log_level,
    )
