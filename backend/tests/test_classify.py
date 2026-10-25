import json

from app import llm
from app.guards import classify as C


def _patch(monkeypatch, *responses):
    it = iter(responses)

    def _chat(model, messages, json_schema=None, **kw):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(llm, "chat", _chat)


OK = json.dumps({"emergency": True, "unsafe": "none", "injection": False, "physical_work": False, "reason": "injury"})


def test_parses_structured_output(monkeypatch):
    _patch(monkeypatch, OK)
    r = C.classify("someone is bleeding")
    assert r.emergency and r.unsafe == "none" and not r.physical_work


def test_tolerates_prose_wrapped_json(monkeypatch):
    _patch(monkeypatch, "Sure!\n```json\n" + OK + "\n```")
    assert C.classify("x").emergency


def test_retries_once_then_returns_none(monkeypatch):
    _patch(monkeypatch, RuntimeError("down"), RuntimeError("down"), "garbage", "garbage")
    assert C.classify("x") is None


def test_recovers_on_second_attempt(monkeypatch):
    _patch(monkeypatch, "garbage", OK)
    assert C.classify("x").emergency


def test_invalid_enum_is_rejected(monkeypatch):
    bad = json.dumps({"emergency": False, "unsafe": "mega-bad", "injection": False, "physical_work": False, "reason": ""})
    _patch(monkeypatch, bad, bad)
    assert C.classify("x") is None
