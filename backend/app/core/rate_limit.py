"""Small in-memory sliding-window rate limiter.

Limits: it lives in ONE server process, so with several workers each has its own counters,
and it resets on restart. Behind a reverse proxy, request.client.host is the proxy's address
unless the proxy is configured properly. Good enough to stop accidental or casual abuse of a
paid API; use a shared store (e.g. Redis) or the gateway's limiter for real production.
"""
import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(
        self,
        max_calls: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds). Counts the call only when allowed."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > self._max_keys:
                self._prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._max_calls:
                return False, max(self._window - (now - hits[0]), 0.0)
            hits.append(now)
            return True, 0.0

    def _prune(self, now: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] >= self._window]
        for k in stale:
            del self._hits[k]
