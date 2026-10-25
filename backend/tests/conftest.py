import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def neutral_classifier(monkeypatch):
    """Router tests mock llm.chat sequentially; keep the nano classifier out of that sequence.

    Tests that care about classification override this with `monkeypatch.setattr(router, "classify", ...)`.
    """
    from app.guards.classify import SafetyClass
    from app.routing import router

    monkeypatch.setattr(router, "classify", lambda *a, **k: SafetyClass())
