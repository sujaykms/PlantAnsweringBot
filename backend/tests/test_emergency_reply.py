from app import answer
from app.contracts import RouteDecision, RouteScore


def _d(searched, emergency):
    return RouteDecision(
        routes=[RouteScore(label="safety", confidence=0.9)], searched=searched, emergency=emergency
    )


def test_emergency_not_found_points_to_people_not_rephrasing():
    text = answer.canned_reply(_d(["safety"], True), not_found=True)
    assert text == answer.EMERGENCY_REPLY
    assert "rephras" not in text.lower()


def test_emergency_with_no_routes_still_gets_emergency_reply():
    assert answer.canned_reply(_d([], True), not_found=False) == answer.EMERGENCY_REPLY


def test_non_emergency_replies_unchanged():
    assert answer.canned_reply(_d(["safety"], False), not_found=True) == answer.NOT_FOUND_REPLY
    assert answer.canned_reply(_d([], False), not_found=False) == answer.NONE_REPLY
    assert answer.canned_reply(_d(["safety"], False), not_found=False) is None
    assert answer.not_found_text(_d(["safety"], True)) == answer.EMERGENCY_REPLY
