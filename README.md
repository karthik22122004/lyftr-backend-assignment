# FastAPI Webhook Ingest Service

Production-ready FastAPI backend implementing an exactly-once WhatsApp-like webhook ingest API, backed by **SQLite**.

## Tech Stack
- Python 3.10+
- FastAPI (async)
- SQLite (file at `/data/app.db` via Docker volume)
- Pydantic validation
- Docker + Docker Compose
- Structured JSON logs (one JSON per line)
- Prometheus-style metrics

---

## Setup Used
VSCode + occasional ChatGPT prompt

## How to run:
## 1. cd to root folder and set Required Environment Variable

cd lyftr-backend-assignment-main/

> Must be set **every new terminal session**

### CMD

```cmd
set WEBHOOK_SECRET=7a612ueyz1
```

### PowerShell

```powershell
$env:WEBHOOK_SECRET="7a612ueyz1"
```

---

## 2️. Clean Everything (Optional but Recommended)

```cmd
docker compose down -v
docker system prune -af
```

---

## 3️. Build Docker Image (No Cache)

```cmd
docker compose build --no-cache
```

---

## 4. Start the API Server

```cmd
docker compose up -d
```

---

## 5. Check Container Status

```cmd
docker compose ps
```

Expected: `api` service → **running** with port `8000`

---

## 6. Check Logs (If Needed)

```cmd
docker compose logs -f api
```

---

##  7. Verify Health Endpoints

```cmd
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

---

## 8️. Run Tests

```cmd
docker compose run --rm api pytest
```

Expected:

```
4 passed
```

---

## 9️. Stop & Clean (When Done)

```cmd
docker compose down -v
```

---


## Environment Variables
- `WEBHOOK_SECRET` (**required**, non-empty)
- `DATABASE_URL` (default: `sqlite:////data/app.db`)
- `LOG_LEVEL` (`INFO` or `DEBUG`)

If `WEBHOOK_SECRET` is missing, `/health/ready` will never return 200.

---

## Run

### Using Docker Compose

```Linux/macOS(bash)

export WEBHOOK_SECRET="7a612ueyz1"
export LOG_LEVEL=INFO

```

```Windows(Powershell)

$env:WEBHOOK_SECRET="7a612ueyz1"

$env:LOG_LEVEL="INFO"

```
```CMD
set WEBHOOK_SECRET=7a612ueyz1
docker compose up -d --build

```

#### Build and start app
```
make up
```

Service will be available at `http://localhost:8000`.

To stop and remove volumes:

```bash
make down
```

Follow logs:

```bash
make logs
```

Run tests:

```bash
make test
```

Verify the App Is Running
Live check (always 200 if running)
curl http://localhost:8000/health/live

Ready check (200 only if DB + schema + secret OK)
curl http://localhost:8000/health/ready


Expected:

{"status":"ready"}

---

## Database
Schema is created automatically on startup.

```sql
CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  from_msisdn TEXT NOT NULL,
  to_msisdn TEXT NOT NULL,
  ts TEXT NOT NULL,
  text TEXT,
  created_at TEXT NOT NULL
);
```

---

## Endpoints

### 1) POST `/webhook`
Ingest a message **exactly once**.

**Signature header**
- `X-Signature = hex(HMAC_SHA256(secret=WEBHOOK_SECRET, raw_request_body))`

Example request:

```bash
body='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'

sig=$(python -c 'import hmac,hashlib,os,sys; body=sys.stdin.read().encode(); print(hmac.new(os.environ["WEBHOOK_SECRET"].encode(), body, hashlib.sha256).hexdigest())' <<<"$body")

curl -s -X POST http://localhost:8000/webhook \
  -H 'Content-Type: application/json' \
  -H "X-Signature: $sig" \
  -d "$body"
```

Response:
```json
{"status":"ok"}
```

**Design decisions**
- **HMAC verification** occurs **before** payload validation so an invalid or missing signature always returns:
  - `401 {"detail":"invalid signature"}`
  - no DB insert
- **Idempotency** uses `message_id` as a primary key; duplicates are handled by catching `sqlite3.IntegrityError` and still returning 200.

---

### 2) GET `/messages`
Query params:
- `limit` (default 50, min 1, max 100)
- `offset` (default 0, min 0)
- `from` (exact match on `from_msisdn`)
- `since` (ISO-8601 UTC string, `ts >= since`)
- `q` (case-insensitive substring match in `text`)

Ordering is mandatory:
- `ORDER BY ts ASC, message_id ASC`

Response:
```json
{
  "data": [...],
  "total": 123,
  "limit": 50,
  "offset": 0
}
```

**Pagination logic**
- `total` is computed using the same filters but ignoring `limit/offset`.

---

### 3) GET `/stats`
Computes:
- `total_messages`
- `senders_count` (distinct `from_msisdn`)
- `messages_per_sender` (top 10, count DESC)
- `first_message_ts` / `last_message_ts` (or null)

**Stats computation**
- Uses SQL aggregates (`COUNT`, `COUNT(DISTINCT ...)`, `MIN`, `MAX`) and a grouped query for top 10 senders.

---

### 4) Health Checks
- `GET /health/live` → always `200` if the process is running
- `GET /health/ready` → `200` only if:
  - DB reachable
  - schema exists
  - `WEBHOOK_SECRET` set
  Otherwise returns `503`.

---

### 5) GET `/metrics`
Prometheus-style plaintext metrics.

Includes:
- `http_requests_total{path,status}`
- `webhook_requests_total{result}`
- `request_latency_seconds` histogram

---

## Logging
One JSON log line per request (jq-parsable). Required fields:
- `ts`, `level`, `request_id`, `method`, `path`, `status`, `latency_ms`

For `/webhook`, logs additionally include:
- `message_id` (if available)
- `dup` (boolean)
- `result` (`created`, `duplicate`, `invalid_signature`, `validation_error`)

---

