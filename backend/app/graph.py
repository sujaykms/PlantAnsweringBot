"""LangGraph orchestration of /chat (everything up to, not including, answer-token streaming).

route -> [canned -> END] | Send x N retrieve_source -> grade -> (rewrite_query -> Send x N ...)
grade -> not_found -> END | generate -> verify -> (generate once more, strict) -> END
The answer is BUFFERED and verified in-graph; main.py only chunks the final text into token events.
"""

import logging
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app import answer, embeddings, llm, retrieval
from app.guards import output as guard
from app.config import get_settings
from app.contracts import (
    DOC_SOURCES,
    ChatTurn,
    RetrievedChunk,
    Verification,
    RouteDecision,
    RouteLabel,
)
from app.routing import router

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


def _merge_hits(old: list | None, new: list | None) -> list:
    """List-append reducer; passing None resets (used by grade between attempts)."""
    if new is None:
        return []
    return (old or []) + new


class ChatState(TypedDict, total=False):
    question: str
    history: list[ChatTurn]
    override: list[RouteLabel] | None
    decision: RouteDecision
    hits: Annotated[list[RetrievedChunk], _merge_hits]  # per-source, reranked
    chunks: list[RetrievedChunk]  # final top_k
    attempts: int
    rewritten_query: str | None
    not_found: bool
    answer: str | None  # canned reply, or the buffered (verified) answer
    verification: Verification | None
    gen_attempts: int
    retry: bool


# ---- nodes ----
def route_node(state: ChatState) -> dict:
    d = router.route(state["question"], state.get("history"), state.get("override"))
    return {"decision": d}


def after_route(state: ChatState):
    d = state["decision"]
    if not d.searched:
        return "canned"
    return _fan_out(state)


def _fan_out(state: ChatState) -> list[Send]:
    q = state.get("rewritten_query") or state["question"]
    return [Send("retrieve_source", {"query": q, "source": s}) for s in state["decision"].searched]


def canned_node(state: ChatState) -> dict:
    return {
        "answer": answer.canned_reply(state["decision"], True),
        "not_found": True,
        "chunks": [],
        "verification": Verification(passed=True),
    }


def not_found_node(state: ChatState) -> dict:
    return {
        "answer": answer.canned_reply(state["decision"], True),
        "verification": Verification(passed=True),
    }


def generate_node(state: ChatState) -> dict:
    n = state.get("gen_attempts", 0) + 1
    text = answer.generate(
        state["question"], state.get("chunks") or [], state["decision"], state.get("history"), strict=n > 1
    )
    return {"answer": text, "gen_attempts": n, "retry": False}


def verify_node(state: ChatState) -> dict:
    v = guard.verify(state.get("answer") or "", state.get("chunks") or [], state["question"], state["decision"])
    n = state.get("gen_attempts", 1)
    v.regenerated = n > 1
    if v.passed:
        return {"verification": v, "retry": False}
    if n < 2:
        log.info("verification failed (%s); regenerating", [c.name for c in v.checks if not c.passed])
        return {"verification": v, "retry": True}
    log.warning("verification failed twice (%s); replacing answer", [c.name for c in v.checks if not c.passed])
    v.replaced = True
    return {
        "verification": v,
        "retry": False,
        "answer": answer.not_found_text(state["decision"]),
        "not_found": True,
    }


def after_verify(state: ChatState) -> str:
    return "generate" if state.get("retry") else END


def retrieve_source_node(payload: dict) -> dict:
    s = get_settings()
    cands = retrieval.hybrid_search(payload["query"], [payload["source"]], s.rerank_candidates)
    if cands:
        scores = embeddings.rerank(payload["query"], [c.content for c in cands])
        for c, sc in zip(cands, scores):
            c.rerank_score = float(sc)
    return {"hits": cands}


def grade_node(state: ChatState) -> dict:
    s = get_settings()
    d = state["decision"]
    hits = state.get("hits") or []
    seen, uniq = set(), []
    for c in hits:
        if c.id not in seen:
            seen.add(c.id)
            uniq.append(c)
    chunks = retrieval.select_top(uniq, list(d.searched), s.top_k)
    attempts = state.get("attempts", 0) + 1
    weak = retrieval._weak(chunks)
    return {
        "chunks": chunks,
        "hits": None,  # reset accumulator for a possible retry
        "attempts": attempts,
        "not_found": weak and attempts >= MAX_ATTEMPTS,
    }


def after_grade(state: ChatState) -> str:
    if retrieval._weak(state.get("chunks") or []) and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "rewrite_query"
    return "not_found_reply" if state.get("not_found") else "generate"


_REWRITE_PROMPT = (
    "Rewrite this plant-floor question as a short, keyword-rich search query for a documentation "
    "search engine. Include equipment IDs, fault codes, part names and synonyms. "
    "Output only the query, no quotes.\n\nQuestion: {q}"
)


def rewrite_node(state: ChatState) -> dict:
    q = state["question"]
    try:
        out = llm.chat(
            get_settings().router_model,
            [{"role": "user", "content": _REWRITE_PROMPT.format(q=q)}],
            max_tokens=60,
        ).strip()
        rewritten = out.splitlines()[0].strip(" \"'") if out else q
    except Exception as e:
        log.warning("rewrite failed: %s", e)
        rewritten = q
    d = state["decision"].model_copy(deep=True)
    # Final attempt widens to everything, unless the user picked the source.
    if not d.overridden and set(d.searched) != set(DOC_SOURCES):
        d.searched = list(DOC_SOURCES)
        d.fallback = True
    return {"rewritten_query": rewritten or q, "decision": d}


def build_graph(checkpointer=None):
    g = StateGraph(ChatState)
    g.add_node("route", route_node)
    g.add_node("canned", canned_node)
    g.add_node("retrieve_source", retrieve_source_node)
    g.add_node("grade", grade_node)
    g.add_node("rewrite_query", rewrite_node)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", after_route, ["canned", "retrieve_source"])
    g.add_edge("canned", END)
    g.add_edge("retrieve_source", "grade")
    g.add_node("not_found_reply", not_found_node)
    g.add_node("generate", generate_node)
    g.add_node("verify", verify_node)
    g.add_conditional_edges("grade", after_grade, ["rewrite_query", "not_found_reply", "generate"])
    g.add_edge("not_found_reply", END)
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", after_verify, ["generate", END])
    g.add_conditional_edges("rewrite_query", _fan_out, ["retrieve_source"])
    return g.compile(checkpointer=checkpointer or MemorySaver())


def make_checkpointer():
    """PostgresSaver on settings.database_url; falls back to MemorySaver if unavailable."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )
        saver = PostgresSaver(pool)
        saver.setup()
        return saver
    except Exception as e:
        log.warning("PostgresSaver unavailable (%s); using MemorySaver", e)
        return MemorySaver()


def initial_input(question: str, history: list[ChatTurn], override) -> dict:
    return {
        "question": question,
        "history": history,
        "override": override,
        "hits": None,
        "chunks": [],
        "attempts": 0,
        "rewritten_query": None,
        "not_found": False,
        "answer": None,
        "verification": None,
        "gen_attempts": 0,
        "retry": False,
    }
