# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN python -m venv /venv \
 && /venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

COPY --from=builder /venv /venv
COPY app ./app
COPY tests ./tests


EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
