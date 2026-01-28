from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError, constr

from .config import get_settings
from .logging_utils import StructLogger, configure_logging
from .metrics import Metrics, now_monotonic
from .models import ISO_UTC_Z_REGEX, MessagesListOut, MessageOut, WebhookMessageIn
from .storage import Storage

settings = get_settings()
logger = StructLogger("api")
metrics = Metrics()
storage = Storage(settings.database_url)

app = FastAPI()


@app.on_event("startup")
async def _startup() -> None:
    configure_logging(settings.log_level)
    # Ensure schema exists (safe to run repeatedly)
    await storage.init_schema()
    logger.info("startup", database_url=settings.database_url)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = now_monotonic()

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        latency_s = now_monotonic() - start
        latency_ms = int(latency_s * 1000)

        path = request.url.path
        metrics.inc_http(path, status_code)
        metrics.observe_latency(latency_s)

        extra: Dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status": status_code,
            "latency_ms": latency_ms,
        }

        # Merge webhook-specific fields if present
        wf = getattr(request.state, "webhook_log_fields", None)
        if isinstance(wf, dict):
            extra.update(wf)

        logger.info("request", **extra)


def _signature_valid(secret: str, body: bytes, provided_hex: str) -> bool:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, provided_hex.strip().lower())


def _validation_422(detail: Any) -> JSONResponse:
    # Mimic FastAPI's general shape: {"detail": [ ... ]}
    if not isinstance(detail, list):
        detail = [detail]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.post("/webhook")
async def webhook(request: Request):
    raw = await request.body()

    # Signature verification MUST happen before payload validation.
    sig = request.headers.get("X-Signature")
    if not sig or not settings.webhook_secret or not _signature_valid(settings.webhook_secret, raw, sig):
        msg_id = None
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
            msg_id = data.get("message_id") if isinstance(data, dict) else None
        except Exception:
            msg_id = None

        request.state.webhook_log_fields = {
            "message_id": msg_id,
            "dup": False,
            "result": "invalid_signature",
        }
        # metrics.inc_webhook("invalid_signature")        return JSONResponse(status_code=401, content={"detail": "invalid signature"})
        metrics.inc_webhook("invalid_signature")
        return JSONResponse(status_code=401, content={"detail": "invalid signature"})

    # Parse JSON
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        request.state.webhook_log_fields = {
            "message_id": None,
            "dup": False,
            "result": "validation_error",
        }
        metrics.inc_webhook("validation_error")
        return _validation_422({"loc": ["body"], "msg": "Invalid JSON", "type": "value_error.jsondecode"})

    # Validate schema via Pydantic
    try:
        msg = WebhookMessageIn.model_validate(payload)
    except ValidationError as e:
        msg_id = payload.get("message_id") if isinstance(payload, dict) else None
        request.state.webhook_log_fields = {
            "message_id": msg_id,
            "dup": False,
            "result": "validation_error",
        }
        metrics.inc_webhook("validation_error")
        return _validation_422(e.errors())

    # Insert exactly once
    ins = await storage.insert_message(
        message_id=msg.message_id,
        from_msisdn=msg.from_msisdn,
        to_msisdn=msg.to_msisdn,
        ts=msg.ts,
        text=msg.text,
    )

    result = "duplicate" if ins.dup else "created"
    request.state.webhook_log_fields = {
        "message_id": msg.message_id,
        "dup": bool(ins.dup),
        "result": result,
    }
    metrics.inc_webhook(result)

    return JSONResponse(status_code=200, content={"status": "ok"})


@app.get("/messages", response_model=MessagesListOut)
async def get_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_msisdn: Optional[str] = Query(None, alias="from"),
    since: Optional[constr(pattern=ISO_UTC_Z_REGEX)] = Query(None),
    q: Optional[str] = Query(None),
):
    page = await storage.list_messages(limit=limit, offset=offset, from_filter=from_msisdn, since=since, q=q)
    data = [MessageOut(**r) for r in page.rows]
    return MessagesListOut(data=data, total=page.total, limit=limit, offset=offset)


@app.get("/stats")
async def get_stats():
    return await storage.stats()


@app.get("/health/live")
async def health_live():
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready():
    # Must be ready ONLY IF DB reachable, schema exists, and WEBHOOK_SECRET set.
    if not settings.webhook_secret:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    try:
        ok = await storage.schema_exists()
        if not ok:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}


@app.get("/metrics")
async def get_metrics():
    return PlainTextResponse(content=metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
