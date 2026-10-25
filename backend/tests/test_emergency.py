"""Emergency alert endpoints, against the local dev Postgres (rows are cleaned up)."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_pool
from app.emergency import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def cleanup():
    ids: list[str] = []
    yield ids
    with get_pool().connection() as conn:
        conn.execute("delete from emergency_alerts where id = any(%s::uuid[])", (ids,))


def test_notify_list_ack_and_idempotency(cleanup):
    mid = str(uuid4())
    body = {"question": "Someone is bleeding on Line 2", "message_id": mid, "location": " Line 2 "}

    first = client.post("/emergency/notify", json=body)
    assert first.status_code == 200
    alert_id = first.json()["alert_id"]
    cleanup.append(alert_id)
    assert first.json()["status"] == "open"

    again = client.post("/emergency/notify", json=body)  # double tap
    assert again.json()["alert_id"] == alert_id

    open_alerts = client.get("/emergency/alerts", params={"status": "open"}).json()
    mine = next(a for a in open_alerts if a["id"] == alert_id)
    assert mine["location"] == "Line 2"  # trimmed

    assert client.post(f"/emergency/alerts/{alert_id}/ack").json() == {"status": "acknowledged"}
    still_open = client.get("/emergency/alerts", params={"status": "open"}).json()
    assert alert_id not in [a["id"] for a in still_open]


def test_validation_and_missing_alert():
    assert client.post("/emergency/notify", json={"question": ""}).status_code == 422
    assert client.post("/emergency/notify", json={"question": "x", "location": "y" * 201}).status_code == 422
    assert client.post(f"/emergency/alerts/{uuid4()}/ack").status_code == 404
