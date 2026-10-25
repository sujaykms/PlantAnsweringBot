import logging
import re
import time

from pydantic import BaseModel

from app import llm
from app.config import get_settings
from app.contracts import DOC_SOURCES, ChatTurn, RouteDecision, RouteLabel, RouteScore
from app.routing.sources import ROUTE_SCHEMA, build_system_prompt

log = logging.getLogger(__name__)

PHYSICAL_VERBS = re.compile(
    r"\b(replac\w*|remov\w*|open\w*|clear\w*|enter\w*|bypass\w*|repair\w*|disassembl\w*|weld\w*)\b",
    re.I,
)
CLOSE_MARGIN = 0.2
LOW_CONF = 0.6


class _ModelOut(BaseModel):
    routes: list[RouteScore]
    reason: str = ""


def _messages(question: str, history: list[ChatTurn] | None) -> list[dict]:
    ctx = ""
    if history:
        ctx = (
            "Previous conversation (for follow-ups):\n"
            + "\n".join(f"{t.role}: {t.content[:300]}" for t in history[-2:])
            + "\n\n"
        )
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": f"{ctx}Question: {question}\nJSON:"},
    ]


def _call_model(model: str, msgs: list[dict]) -> _ModelOut:
    try:
        raw = llm.chat(model, msgs, json_schema=ROUTE_SCHEMA, max_tokens=200)
    except Exception as e:  # provider may reject json_schema
        log.info("json_schema call failed (%s); retrying without schema", e)
        raw = llm.chat(model, msgs, max_tokens=200)
    return _ModelOut.model_validate(llm.parse_json(raw))


def apply_rules(question: str, routes: list[RouteScore]) -> list[RouteLabel]:
    ranked = sorted(routes, key=lambda r: r.confidence, reverse=True)
    if not ranked or ranked[0].label == "none":
        return []
    docs = [r for r in ranked if r.label in DOC_SOURCES]  # analytics not routed until Phase 3
    if not docs:
        return list(DOC_SOURCES)
    searched: list[RouteLabel] = [docs[0].label]
    top = docs[0].confidence
    if len(docs) > 1 and (top - docs[1].confidence <= CLOSE_MARGIN or top < LOW_CONF):
        searched.append(docs[1].label)
    if PHYSICAL_VERBS.search(question) and "safety" not in searched:
        searched.append("safety")
    return searched


def route(
    question: str,
    history: list[ChatTurn] | None = None,
    override: list[RouteLabel] | None = None,
    model: str | None = None,
) -> RouteDecision:
    if override:
        return RouteDecision(
            routes=[RouteScore(label=l, confidence=1.0) for l in override],
            reason="user override",
            searched=list(override),
            overridden=True,
        )
    model = model or get_settings().router_model
    t0 = time.perf_counter()
    out: _ModelOut | None = None
    msgs = _messages(question, history)
    for attempt in range(2):
        try:
            out = _call_model(model, msgs)
            break
        except Exception as e:
            log.warning("router attempt %d failed: %s", attempt + 1, e)
    ms = int((time.perf_counter() - t0) * 1000)
    if out is None:
        return RouteDecision(
            routes=[], reason="router failed; searching all sources",
            searched=list(DOC_SOURCES), fallback=True, model=model, latency_ms=ms,
        )
    return RouteDecision(
        routes=out.routes, reason=out.reason, searched=apply_rules(question, out.routes),
        model=model, latency_ms=ms,
    )
