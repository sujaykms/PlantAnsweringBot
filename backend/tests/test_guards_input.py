import threading

import pytest

from app.contracts import ChatTurn
from app.guards.input import InputRejected, RateLimiter, sanitize_history, validate_message


def test_validate_collapses_whitespace_and_strips():
    assert validate_message("  hello \n\t  world\x00 ") == "hello world"


@pytest.mark.parametrize("bad", ["", "   \n\t", "\x00\x01"])
def test_validate_rejects_empty(bad):
    with pytest.raises(InputRejected):
        validate_message(bad)


def test_validate_length_limit():
    assert len(validate_message("a" * 1500)) == 1500
    with pytest.raises(InputRejected) as e:
        validate_message("a" * 1501)
    assert e.value.reason and isinstance(e.value, ValueError)


def test_rate_limiter_sliding_window():
    t = [0.0]
    rl = RateLimiter(max_requests=3, window_s=10, clock=lambda: t[0])
    assert [rl.check("a") for _ in range(4)] == [True, True, True, False]
    assert rl.check("b")  # independent key
    t[0] = 10.5
    assert rl.check("a")


def test_rate_limiter_thread_safe():
    rl = RateLimiter(max_requests=50, window_s=60)
    results: list[bool] = []

    def hit():
        for _ in range(20):
            results.append(rl.check("k"))

    ts = [threading.Thread(target=hit) for _ in range(10)]
    [x.start() for x in ts]
    [x.join() for x in ts]
    assert sum(results) == 50


def test_sanitize_history():
    h = [ChatTurn(role="user" if i % 2 == 0 else "assistant", content=f" t{i}  x ") for i in range(10)]
    h.append(ChatTurn(role="user", content="   "))
    h.append(ChatTurn(role="assistant", content="z" * 5000))
    out = sanitize_history(h)
    assert len(out) <= 6 and out[-1].content == "z" * 1500
    assert all(t.content == t.content.strip() for t in out)
    assert sanitize_history(h, max_turns=0) == []
