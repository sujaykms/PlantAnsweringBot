"""LLM-backed eval smoke tests. Skipped by default; run with: uv run pytest -m evals"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

pytestmark = pytest.mark.evals


def test_judge_family_differs_from_answer_model():
    from app.config import get_settings
    from evals.judge import judge_model_name

    assert judge_model_name().split("/")[0] != get_settings().answer_model.split("/")[0]


@pytest.fixture(scope="module")
def judge():
    from app.config import get_settings

    if not get_settings().openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")
    from evals.judge import OpenRouterJudge

    return OpenRouterJudge()


def test_faithfulness_separates_grounded_from_hallucinated(judge):
    from deepeval.metrics import FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    ctx = ["Impeller nut: M20 left-hand thread, torque 95 N·m."]
    good = LLMTestCase(input="Impeller nut torque?", actual_output="95 N·m.", retrieval_context=ctx)
    bad = LLMTestCase(input="Impeller nut torque?", actual_output="The torque is 150 N·m and uses a right-hand thread.", retrieval_context=ctx)
    m = FaithfulnessMetric(model=judge, async_mode=False, include_reason=False)
    m.measure(good)
    g = m.score
    m.measure(bad)
    assert g > m.score


def test_router_routes_offtopic_to_none():
    from app.routing.router import route

    assert route("What's on the cafeteria menu today?").searched == []
