import logging
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from app import llm
from app.config import get_settings
from app.contracts import DOC_SOURCES, ChatTurn, RouteDecision, RouteLabel, RouteScore
from app.guards.classify import SafetyClass, classify
from app.routing.sources import ROUTE_SCHEMA, build_system_prompt

log = logging.getLogger(__name__)

CLOSE_MARGIN = 0.2
LOW_CONF = 0.6


_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="classify")
HARMFUL = {"falsify_records", "sabotage", "other_harm"}


class _ModelOut(BaseModel):
    routes: list[RouteScore]
    reason: str = ""
    emergency: bool = False


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


def apply_rules(routes: list[RouteScore], physical_work: bool = False) -> list[RouteLabel]:
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
    if physical_work and "safety" not in searched:
        searched.append("safety")
    return searched


def _apply_safety(searched: list[RouteLabel], cls: SafetyClass | None) -> list[RouteLabel]:
    """Fold the classifier's verdict into the routing decision."""
    if cls is None:
        return searched
    if cls.injection or cls.unsafe in HARMFUL:
        return []  # canned reply, no retrieval (emergencies still get the emergency reply)
    if cls.unsafe == "bypass_safety" and "safety" not in searched:
        return [*searched, "safety"]  # answer with the rule and the safe alternative, cited
    return searched


def _flags(cls: SafetyClass | None, router_emergency: bool = False) -> dict:
    return {
        "emergency": router_emergency or bool(cls and cls.emergency),
        "unsafe": cls.unsafe if cls else "none",
        "injection": bool(cls and cls.injection),
        "physical_work": cls.physical_work if cls else None,
    }


def route(
    question: str,
    history: list[ChatTurn] | None = None,
    override: list[RouteLabel] | None = None,
    model: str | None = None,
) -> RouteDecision:
    cls_future = _pool.submit(classify, question, history)  # nano classifier, parallel to the router
    if override:
        cls = cls_future.result()
        return RouteDecision(
            routes=[RouteScore(label=l, confidence=1.0) for l in override],
            reason="user override",
            searched=list(override),
            overridden=True,
            **_flags(cls),
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
    cls = cls_future.result()
    ms = int((time.perf_counter() - t0) * 1000)
    if out is None:
        return RouteDecision(
            routes=[], reason="router failed; searching all sources",
            searched=_apply_safety(list(DOC_SOURCES), cls), fallback=True, model=model, latency_ms=ms,
            **_flags(cls),
        )
    searched = _apply_safety(apply_rules(out.routes, bool(cls and cls.physical_work)), cls)
    return RouteDecision(
        routes=out.routes, reason=out.reason, searched=searched, model=model, latency_ms=ms,
        **_flags(cls, router_emergency=out.emergency),
    )
