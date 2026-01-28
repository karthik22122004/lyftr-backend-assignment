import hashlib
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for `import app`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import hmac
import importlib

import pytest
from fastapi.testclient import TestClient


def make_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:////{db_path}")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    import app.main as main
    importlib.reload(main)

    with TestClient(main.app) as c:
        yield c
