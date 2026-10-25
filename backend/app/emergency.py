"""Operator alerts: a supervisor confirms in the UI, the alert is stored for the operator view.

V1 stores alerts and shows them on /operator; no external delivery (SMS/Slack/webhook) yet.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import get_pool

router = APIRouter(prefix="/emergency", tags=["emergency"])

COLUMNS = "id, created_at, question, location, status, acknowledged_at"


class NotifyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    location: str | None = Field(default=None, max_length=200)


class NotifyResponse(BaseModel):
    alert_id: UUID
    status: Literal["open", "acknowledged"]
    created_at: datetime


class Alert(BaseModel):
    id: UUID
    created_at: datetime
    question: str
    location: str | None
    status: Literal["open", "acknowledged"]
    acknowledged_at: datetime | None


@router.post("/notify", response_model=NotifyResponse)
def notify(req: NotifyRequest) -> NotifyResponse:
    location = (req.location or "").strip() or None
    with get_pool().connection() as conn:
        # Idempotent per message: a repeat tap returns the existing alert.
        row = conn.execute(
            """
            insert into emergency_alerts (conversation_id, message_id, question, location)
            values (%s, %s, %s, %s)
            on conflict (message_id) where message_id is not null do nothing
            returning id, status, created_at
            """,
            (req.conversation_id, req.message_id, req.question.strip(), location),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "select id, status, created_at from emergency_alerts where message_id = %s",
                (req.message_id,),
            ).fetchone()
    return NotifyResponse(alert_id=row["id"], status=row["status"], created_at=row["created_at"])


@router.get("/alerts", response_model=list[Alert])
def list_alerts(status: Literal["open", "acknowledged"] | None = None, limit: int = 50) -> list[Alert]:
    limit = max(1, min(limit, 200))
    sql = f"select {COLUMNS} from emergency_alerts"
    params: list = []
    if status:
        sql += " where status = %s"
        params.append(status)
    sql += " order by created_at desc limit %s"
    params.append(limit)
    with get_pool().connection() as conn:
        return [Alert(**r) for r in conn.execute(sql, params).fetchall()]


@router.post("/alerts/{alert_id}/ack")
def acknowledge(alert_id: UUID) -> dict:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            update emergency_alerts
               set status = 'acknowledged', acknowledged_at = coalesce(acknowledged_at, now())
             where id = %s
            returning id
            """,
            (alert_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return {"status": "acknowledged"}
