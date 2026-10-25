import uuid

from app import embeddings, graph, llm, retrieval
from app.contracts import RetrievedChunk, RouteDecision, RouteScore
from app.routing import router


def ch(source):
    return RetrievedChunk(
        id=uuid.uuid4(), document_id=uuid.uuid4(), source=source, title="t",
        section_path="s", content=source, score=0.01,
    )


def run(q="q", monkeypatch=None):
    monkeypatch.setattr(llm, "chat_stream", lambda *a, **k: iter(["Not in the documentation."]))
    g = graph.build_graph()
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    return g.invoke(graph.initial_input(q, [], None), cfg)


def decision(*labels):
    return RouteDecision(routes=[RouteScore(label=l, confidence=0.9) for l in labels], searched=list(labels))


def test_none_goes_to_canned(monkeypatch):
    monkeypatch.setattr(router, "route", lambda *a, **k: RouteDecision(routes=[], searched=[]))
    called = []
    monkeypatch.setattr(retrieval, "hybrid_search", lambda *a: called.append(1) or [])
    out = run(monkeypatch=monkeypatch)
    assert out["answer"] and out["not_found"] and not called


def test_fanout_merge_with_per_source_guarantee(monkeypatch):
    monkeypatch.setattr(router, "route", lambda *a, **k: decision("maintenance", "safety"))
    searched = []

    def hs(q, sources, k):
        searched.append(sources[0])
        return [ch(sources[0]) for _ in range(8)]

    scores = {"maintenance": [9, 8, 7, 6, 5, 4, 3, 2], "safety": [-1, -2, -3, -4, -5, -6, -7, -8]}
    monkeypatch.setattr(retrieval, "hybrid_search", hs)
    monkeypatch.setattr(embeddings, "rerank", lambda q, p: [float(x) for x in scores[p[0]]])
    out = run(monkeypatch=monkeypatch)
    assert sorted(searched) == ["maintenance", "safety"]
    assert len(out["chunks"]) == 6 and sum(c.source == "safety" for c in out["chunks"]) == 2
    assert not out["not_found"] and out["attempts"] == 1


def test_low_score_rewrites_then_widens(monkeypatch):
    monkeypatch.setattr(router, "route", lambda *a, **k: decision("quality"))
    queries = []

    def hs(q, sources, k):
        queries.append((q, sources[0]))
        return [ch(sources[0])]

    monkeypatch.setattr(retrieval, "hybrid_search", hs)
    monkeypatch.setattr(embeddings, "rerank", lambda q, p: [5.0 if q == "kw query" else -9.0] * len(p))
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "kw query")
    out = run("vague", monkeypatch)
    assert queries[0] == ("vague", "quality")
    assert {s for _, s in queries[1:]} == {"safety", "maintenance", "quality"}
    assert all(q == "kw query" for q, _ in queries[1:])
    assert out["decision"].fallback and not out["not_found"] and out["attempts"] == 2


def test_not_found_after_retries(monkeypatch):
    monkeypatch.setattr(router, "route", lambda *a, **k: decision("quality"))
    monkeypatch.setattr(retrieval, "hybrid_search", lambda q, s, k: [ch(s[0])])
    monkeypatch.setattr(embeddings, "rerank", lambda q, p: [-9.0] * len(p))
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "kw")
    out = run(monkeypatch=monkeypatch)
    assert out["not_found"] and out["attempts"] == 2
