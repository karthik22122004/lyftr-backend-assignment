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


def test_stats(client):
    _post(client, {
        "message_id": "m1",
        "from": "+111",
        "to": "+222",
        "ts": "2025-01-15T10:00:00Z",
        "text": "A",
    })
    _post(client, {
        "message_id": "m2",
        "from": "+111",
        "to": "+222",
        "ts": "2025-01-15T10:01:00Z",
        "text": "B",
    })
    _post(client, {
        "message_id": "m3",
        "from": "+333",
        "to": "+222",
        "ts": "2025-01-15T10:02:00Z",
        "text": "C",
    })

    r = client.get("/stats")
    assert r.status_code == 200
    s = r.json()
    assert s["total_messages"] == 3
    assert s["senders_count"] == 2
    assert s["first_message_ts"] == "2025-01-15T10:00:00Z"
    assert s["last_message_ts"] == "2025-01-15T10:02:00Z"
    assert s["messages_per_sender"][0]["from"] == "+111"
    assert s["messages_per_sender"][0]["count"] == 2
