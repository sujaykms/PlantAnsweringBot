import json

import pytest

from app import llm
from app.routing import router
from app.routing.sources import EMERGENCY_EXAMPLES, EXAMPLES


def _fake(emergency=None, label="safety"):
    d = {"routes": [{"label": label, "confidence": 0.9}], "reason": "r"}
    if emergency is not None:
        d["emergency"] = emergency
    return json.dumps(d)


@pytest.fixture
def chat(monkeypatch):
    def _set(*responses):
        it = iter(responses)

        def _chat(model, messages, json_schema=None, **kw):
            r = next(it)
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(llm, "chat", _chat)

    return _set


def test_model_flag_is_used(chat):
    chat(_fake(True))
    d = router.route("Worker is acting strange near the tank")
    assert d.emergency and d.searched == ["safety"]


def test_default_false(chat):
    chat(_fake(False))
    assert not router.route("What PPE do I need on the paint line?").emergency


def test_missing_flag_defaults_false(chat):
    chat(_fake(None))
    assert not router.route("What PPE do I need?").emergency


def test_backstop_overrides_model_miss(chat):
    chat(_fake(False))
    d = router.route("Someone is bleeding from the arm")
    assert d.emergency and d.searched == ["safety"]  # still routed normally


def test_backstop_on_llm_failure(chat):
    chat("garbage", RuntimeError("down"))
    d = router.route("There is a fire in the paint booth")
    assert d.fallback and d.emergency and d.searched == ["safety", "maintenance", "quality"]


def test_no_backstop_on_failure_for_normal_question(chat):
    chat("garbage", "garbage")
    assert not router.route("What PPE do I need?").emergency


def test_backstop_applies_with_override(chat):
    chat()
    d = router.route("gas alarm is going off", override=["maintenance"])
    assert d.overridden and d.emergency


@pytest.mark.parametrize("q", sorted(EMERGENCY_EXAMPLES))
def test_backstop_catches_example_set(q):
    assert router.detect_emergency(q)


@pytest.mark.parametrize(
    "q",
    [q for q, _ in EXAMPLES if q not in EMERGENCY_EXAMPLES]
    + [
        "Where is the fire extinguisher inspection schedule?",
        "What is the fire drill procedure for annual training?",
        "How often is the fire door inspected?",
    ],
)
def test_backstop_no_false_positive(q):
    assert not router.detect_emergency(q)


@pytest.mark.parametrize(
    "q",
    [
        "Someone is unconscious",
        "he got burned by steam",
        "chemical spill in bay 4",
        "smell gas near boiler",
        "electric shock from panel",
        "Worker trapped under the pallet",
        "oil on fire",
        "acid in her eyes",
    ],
)
def test_backstop_terms(q):
    assert router.detect_emergency(q)


def test_prompt_and_schema_include_emergency():
    from app.routing.sources import ROUTE_SCHEMA, build_system_prompt

    assert "emergency" in ROUTE_SCHEMA["properties"] and "emergency" in ROUTE_SCHEMA["required"]
    assert '"emergency":true' in build_system_prompt()
