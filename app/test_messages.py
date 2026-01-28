import json

from conftest import make_sig


def _post(client, body):
    raw = json.dumps(body).encode("utf-8")
    sig = make_sig("test-secret", raw)
    r = client.post(
        "/webhook",
        data=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200


def test_messages_pagination_order_filters(client):
    _post(client, {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello Alpha",
    })
    _post(client, {
        "message_id": "m2",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "hello beta",
    })
    _post(client, {
        "message_id": "m3",
        "from": "+14155550100",
        "to": "+919876543210",
        "ts": "2025-01-15T11:00:00Z",
        "text": "Gamma",
    })

    r = client.get("/messages", params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert [m["message_id"] for m in data["data"]] == ["m1", "m2"]

    r2 = client.get("/messages", params={"limit": 2, "offset": 2})
    assert r2.status_code == 200
    assert [m["message_id"] for m in r2.json()["data"]] == ["m3"]

    r3 = client.get("/messages", params={"from": "+14155550100"})
    assert r3.status_code == 200
    assert r3.json()["total"] == 1

    r4 = client.get("/messages", params={"since": "2025-01-15T11:00:00Z"})
    assert r4.status_code == 200
    assert [m["message_id"] for m in r4.json()["data"]] == ["m3"]

    r5 = client.get("/messages", params={"q": "ALPHA"})
    assert r5.status_code == 200
    assert r5.json()["total"] == 1
    assert r5.json()["data"][0]["message_id"] == "m1"
