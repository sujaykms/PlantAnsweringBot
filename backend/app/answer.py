from collections.abc import Iterator

from app import llm
from app.config import get_settings
from app.contracts import ChatTurn, RetrievedChunk, RouteDecision

SYSTEM = """You are a plant documentation assistant for floor supervisors.
Answer ONLY from the provided documentation excerpts. Do not use outside knowledge.
- Be concise. Use numbered steps when the answer is procedural.
- Cite sources inline as [Doc Title §section-number], using the excerpt's title and section number.
- If the excerpts include safety content relevant to the task, start with a short line beginning "⚠️ Safety:".
- If the excerpts do not answer the question, say it is not in the documentation and suggest which source/team to check (safety, maintenance, or quality)."""

NOT_FOUND_REPLY = (
    "I couldn't find this in the plant documentation. Try rephrasing with an equipment ID "
    "or document name, or check with the relevant team (safety, maintenance, or quality)."
)
NONE_REPLY = (
    "That doesn't look like a plant documentation question. I can help with safety, "
    "maintenance, and quality procedures, specs, and fault codes."
)


def canned_reply(decision: RouteDecision, not_found: bool) -> str | None:
    if not decision.searched:
        return NONE_REPLY
    if not_found:
        return NOT_FOUND_REPLY
    return None


def build_messages(
    question: str, chunks: list[RetrievedChunk], history: list[ChatTurn] | None = None
) -> list[dict]:
    ctx = "\n\n".join(
        f"[Excerpt {i}] {c.title} | {c.section_path}"
        + (f" | p.{c.page}" if c.page else "")
        + f" | source: {c.source}\n{c.content}"
        for i, c in enumerate(chunks, 1)
    )
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": t.role, "content": t.content} for t in (history or [])[-4:]]
    msgs.append({"role": "user", "content": f"Documentation excerpts:\n{ctx}\n\nQuestion: {question}"})
    return msgs


def stream_answer(
    question: str,
    chunks: list[RetrievedChunk],
    decision: RouteDecision,
    not_found: bool,
    history: list[ChatTurn] | None = None,
) -> Iterator[str]:
    canned = canned_reply(decision, not_found)
    if canned is not None:
        yield canned
        return
    yield from llm.chat_stream(get_settings().answer_model, build_messages(question, chunks, history))
