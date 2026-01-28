import json

from conftest import make_sig


def test_webhook_invalid_signature(client):
    body = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello",
    }
    raw = json.dumps(body).encode("utf-8")
    r = client.post(
        "/webhook",
        data=raw,
        headers={"Content-Type": "application/json", "X-Signature": "bad"},
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "invalid signature"}


def test_webhook_created_and_duplicate(client):
    body = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello",
    }
    raw = json.dumps(body).encode("utf-8")
    sig = make_sig("test-secret", raw)

    r1 = client.post(
        "/webhook",
        data=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r1.status_code == 200
    assert r1.json() == {"status": "ok"}

    r2 = client.post(
        "/webhook",
        data=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r2.status_code == 200
    assert r2.json() == {"status": "ok"}
