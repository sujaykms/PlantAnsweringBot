import json

import pytest

from app import llm
from app.routing import router


def fake(routes, reason="r"):
    return json.dumps({"routes": [{"label": l, "confidence": c} for l, c in routes], "reason": reason})


@pytest.fixture
def mock_chat(monkeypatch):
    def _set(*responses):
        calls = []
        it = iter(responses)

        def _chat(model, messages, json_schema=None, **kw):
            calls.append((model, messages, json_schema))
            r = next(it)
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(llm, "chat", _chat)
        return calls

    return _set


def test_single_confident_label(mock_chat):
    mock_chat(fake([("maintenance", 0.95), ("quality", 0.2)]))
    d = router.route("Conveyor 3 is showing fault E42")
    assert d.searched == ["maintenance"] and not d.fallback and d.model


def test_second_label_within_margin(mock_chat):
    mock_chat(fake([("quality", 0.8), ("maintenance", 0.65)]))
    assert router.route("Parts have burrs since the die change").searched == ["quality", "maintenance"]


def test_second_label_when_top_low(mock_chat):
    mock_chat(fake([("quality", 0.5), ("safety", 0.1)]))
    assert router.route("something vague").searched == ["quality", "safety"]


def test_physical_verb_adds_safety(mock_chat):
    mock_chat(fake([("maintenance", 0.95)]))
    assert router.route("How do I replace the compressor filter?").searched == ["maintenance", "safety"]


def test_none_alone_searches_nothing(mock_chat):
    mock_chat(fake([("none", 0.9)]))
    assert router.route("What's on the cafeteria menu?").searched == []


def test_analytics_not_routed(mock_chat):
    mock_chat(fake([("analytics", 0.9), ("quality", 0.85)]))
    assert "analytics" not in router.route("how many defects last week").searched


def test_parse_failure_retries_then_succeeds(mock_chat):
    calls = mock_chat("not json at all", fake([("safety", 0.9)]))
    d = router.route("What PPE do I need?")
    assert d.searched == ["safety"] and len(calls) == 2


def test_schema_error_retries_without_schema(mock_chat):
    calls = mock_chat(RuntimeError("response_format unsupported"), "```json\n" + fake([("safety", 0.9)]) + "\n```")
    d = router.route("What PPE do I need?")
    assert d.searched == ["safety"]
    assert calls[0][2] is not None and calls[1][2] is None


def test_total_failure_falls_back_to_all(mock_chat):
    mock_chat("garbage", "more garbage")
    d = router.route("anything")
    assert d.fallback and d.searched == ["safety", "maintenance", "quality"]


def test_override_skips_model(mock_chat):
    calls = mock_chat()
    d = router.route("q", override=["quality"])
    assert d.overridden and d.searched == ["quality"] and calls == []


def test_history_included(mock_chat):
    from app.contracts import ChatTurn

    calls = mock_chat(fake([("safety", 0.9)]))
    hist = [ChatTurn(role="user", content=f"turn{i}") for i in range(4)]
    router.route("and then?", history=hist)
    user_msg = calls[0][1][-1]["content"]
    assert "turn3" in user_msg and "turn2" in user_msg and "turn1" not in user_msg
