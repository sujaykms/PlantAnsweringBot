from uuid import UUID

from psycopg.types.json import Jsonb

from app import db
from app.contracts import RouteDecision, Verification


def save_turn(
    conversation_id: UUID | None,
    question: str,
    answer: str,
    decision: RouteDecision,
    cited_chunk_ids: list[UUID],
    verification: Verification | None = None,
) -> tuple[UUID, UUID]:
    """Persist user + assistant messages. Returns (conversation_id, assistant_message_id)."""
    route = decision.model_dump(mode="json")
    if verification is not None:
        route["verification"] = verification.model_dump(mode="json")
    with db.get_pool().connection() as conn:
        if conversation_id is not None:
            row = conn.execute("select id from conversations where id = %s", (conversation_id,)).fetchone()
            if row is None:
                conn.execute("insert into conversations (id) values (%s)", (conversation_id,))
        else:
            conversation_id = conn.execute("insert into conversations default values returning id").fetchone()["id"]
        conn.execute(
            "insert into messages (conversation_id, role, content) values (%s, 'user', %s)",
            (conversation_id, question),
        )
        mid = conn.execute(
            "insert into messages (conversation_id, role, content, route, cited_chunk_ids) "
            "values (%s, 'assistant', %s, %s, %s) returning id",
            (conversation_id, answer, Jsonb(route), cited_chunk_ids),
        ).fetchone()["id"]
    return conversation_id, mid
