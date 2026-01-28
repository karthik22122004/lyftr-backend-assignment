import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 with Z suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JsonFormatter(logging.Formatter):
    """JSON log formatter: one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Allow structured extras under record.extra
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in payload:
                    payload[k] = v

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Remove default handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


class StructLogger:
    """Convenience wrapper around stdlib logging."""

    def __init__(self, name: str = "app"):
        self._logger = logging.getLogger(name)

    def info(self, message: str, **fields: Any) -> None:
        self._logger.info(message, extra={"extra": fields})

    def debug(self, message: str, **fields: Any) -> None:
        self._logger.debug(message, extra={"extra": fields})

    def warning(self, message: str, **fields: Any) -> None:
        self._logger.warning(message, extra={"extra": fields})

    def error(self, message: str, **fields: Any) -> None:
        self._logger.error(message, extra={"extra": fields})

    def exception(self, message: str, **fields: Any) -> None:
        self._logger.exception(message, extra={"extra": fields})
