"""Input guards: message validation, per-key rate limiting, history sanitising. No FastAPI imports."""

import re
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from app.contracts import ChatTurn

MAX_MESSAGE_CHARS = 1500
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS = re.compile(r"\s+")


class InputRejected(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _clean(text: str) -> str:
    return _WS.sub(" ", _CTRL.sub("", text)).strip()


def validate_message(text: str) -> str:
    if not isinstance(text, str):
        raise InputRejected("Message must be text.")
    cleaned = _clean(text)
    if not cleaned:
        raise InputRejected("Message is empty.")
    if len(cleaned) > MAX_MESSAGE_CHARS:
        raise InputRejected(f"Message is too long (max {MAX_MESSAGE_CHARS} characters).")
    return cleaned


class RateLimiter:
    """In-memory sliding-window limiter; thread-safe."""

    def __init__(self, max_requests: int = 20, window_s: float = 60, clock: Callable[[], float] = time.monotonic):
        self.max_requests = max_requests
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Record a request; return False if the key is over its limit."""
        now = self._clock()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self.window_s:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            if len(self._hits) > 10_000:  # opportunistic cleanup of idle keys
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window_s]:
                    del self._hits[k]
            return True


def sanitize_history(history: list[ChatTurn], max_turns: int = 6, max_chars: int = 1500) -> list[ChatTurn]:
    """Keep the last max_turns non-empty turns, cleaned and truncated."""
    out: list[ChatTurn] = []
    for t in history[-max_turns:] if max_turns > 0 else []:
        if t.role not in ("user", "assistant"):
            continue
        c = _clean(t.content)[:max_chars]
        if c:
            out.append(ChatTurn(role=t.role, content=c))
    return out


def client_key(forwarded_for: str | None, peer: str | None) -> str:
    """Rate-limit key: the visitor behind the proxy (first X-Forwarded-For hop), else the socket peer."""
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return peer or "unknown"
