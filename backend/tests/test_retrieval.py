import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import answer, embeddings, main, retrieval, store
from app.contracts import RetrievedChunk, RouteDecision, RouteScore
from app.routing import router


def chunk(source, score):
    return RetrievedChunk(
        id=uuid.uuid4(), document_id=uuid.uuid4(), source=source, title=f"{source} doc",
        section_path="A > 1 Intro", content=f"{source} text", score=0.01, rerank_score=score,
    )


def test_extract_equipment():
    assert retrieval.extract_equipment("torque for p-101 and BRK-200?") == ["BRK-200", "P-101"]


def test_per_source_guarantee():
    cs = [chunk("maintenance", 9 - i) for i in range(8)] + [chunk("safety", -1), chunk("safety", -2)]
    out = retrieval.select_top(cs, ["maintenance", "safety"], 6)
    assert len(out) == 6 and sum(c.source == "safety" for c in out) == 2
    assert [c.rerank_score for c in out] == sorted((c.rerank_score for c in out), reverse=True)


def test_single_source_no_guarantee():
    cs = [chunk("quality", i) for i in range(10)]
    assert len(retrieval.select_top(cs, ["quality"], 6)) == 6


def test_retrieve_hybrid_then_rerank(monkeypatch):
    order = []
    cands = [chunk("safety", None) for _ in range(3)]

    def hs(q, sources, k):
        order.append(("hybrid", k))
        return cands

    def rr(q, passages):
        order.append(("rerank", len(passages)))
        return [1.0, 3.0, 2.0]

    monkeypatch.setattr(retrieval, "hybrid_search", hs)
    monkeypatch.setattr(embeddings, "rerank", rr)
    out = retrieval.retrieve("q", ["safety"])
    assert order == [("hybrid", 20), ("rerank", 3)]
    assert [c.rerank_score for c in out] == [3.0, 2.0, 1.0]


def _patch_by_source(monkeypatch, table):
    def retr(q, sources):
        return [c for s in sources for c in table.get(s, [])]

    monkeypatch.setattr(retrieval, "retrieve", retr)


def test_fallback_widens_on_weak(monkeypatch):
    _patch_by_source(monkeypatch, {"quality": [chunk("quality", -9)], "safety": [chunk("safety", 4)]})
    d = RouteDecision(routes=[], searched=["quality"])
    chunks, nf = retrieval.retrieve_with_fallback("q", d)
    assert d.fallback and set(d.searched) == {"safety", "maintenance", "quality"} and not nf
    assert chunks


def test_fallback_not_found(monkeypatch):
    _patch_by_source(monkeypatch, {})
    d = RouteDecision(routes=[], searched=["quality"])
    _, nf = retrieval.retrieve_with_fallback("q", d)
    assert nf and d.fallback


def test_no_fallback_when_good(monkeypatch):
    _patch_by_source(monkeypatch, {"quality": [chunk("quality", 5)]})
    d = RouteDecision(routes=[], searched=["quality"])
    _, nf = retrieval.retrieve_with_fallback("q", d)
    assert not nf and not d.fallback


# ---- /chat SSE ----
@pytest.fixture
def client(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    from app import graph

    monkeypatch.setattr(embeddings, "warm_up", lambda: None)
    monkeypatch.setattr(graph, "make_checkpointer", lambda: MemorySaver())
    dec = RouteDecision(routes=[RouteScore(label="safety", confidence=0.9)], searched=["safety"])
    monkeypatch.setattr(router, "route", lambda q, h=None, o=None: dec.model_copy(deep=True))
    monkeypatch.setattr(retrieval, "hybrid_search", lambda q, s, k: [chunk(s[0], None)])
    monkeypatch.setattr(embeddings, "rerank", lambda q, p: [3.0] * len(p))
    monkeypatch.setattr(answer.llm, "chat_stream", lambda m, msgs: iter(["Wear gloves ", "[safety doc §1]."]))
    cid, mid = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(store, "save_turn", lambda *a, **k: (cid, mid))
    with TestClient(main.app) as c:
        yield c


def events(resp):
    out, ev = [], None
    for line in resp.text.splitlines():
        if line.startswith("event:"):
            ev = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((ev, json.loads(line.split(":", 1)[1])))
    return out


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_event_order(client):
    r = client.post("/chat", json={"message": "What PPE?"})
    evs = events(r)
    kinds = [e for e, _ in evs if e != "status"]
    assert kinds[:2] == ["route", "sources"] and kinds[-1] == "done" and set(kinds[2:-1]) == {"token"}
    assert [d["stage"] for e, d in evs if e == "status"] == ["routing", "retrieving", "generating", "verifying"]
    assert dict(evs)["route"]["searched"] == ["safety"]
    assert len(dict(evs)["sources"]["chunks"]) == 1
    assert evs[-1][1]["verification"]["passed"] is True
    assert evs[-1][1]["not_found"] is False


def test_chat_none_route_canned(client, monkeypatch):
    dec = RouteDecision(routes=[RouteScore(label="none", confidence=0.9)], searched=[])
    monkeypatch.setattr(router, "route", lambda q, h=None, o=None: dec)
    evs = events(client.post("/chat", json={"message": "menu?"}))
    evs = [x for x in evs if x[0] != "status"]
    assert "".join(d["text"] for e, d in evs if e == "token") == answer.NONE_REPLY
    assert evs[0][0] == "route" and evs[1][0] == "sources" and evs[-1][0] == "done"
    assert evs[-1][1]["not_found"] is True


def test_chat_error_event(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(retrieval, "hybrid_search", boom)
    evs = events(client.post("/chat", json={"message": "x"}))
    assert evs[-1][0] == "error" and "db down" in evs[-1][1]["message"]
