"""
Per-vendor Circuit Breaker.
States: CLOSED (normal) → OPEN (failing, all calls skipped) → HALF_OPEN (probe single call)
Sliding window: count failures in the last WINDOW_SEC. If >= THRESHOLD, trip OPEN.
After COOLDOWN_SEC in OPEN, transition to HALF_OPEN. A successful probe → CLOSED.
A failed probe → OPEN again.
"""
from __future__ import annotations
import os
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Literal

State = Literal["closed", "open", "half_open"]

THRESHOLD = int(os.environ.get("CB_THRESHOLD", "5"))
WINDOW_SEC = int(os.environ.get("CB_WINDOW_SEC", "60"))
COOLDOWN_SEC = int(os.environ.get("CB_COOLDOWN_SEC", "30"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CircuitBreaker:
    """Process-local breaker (one per backend instance). For multi-replica
    deployments, externalize state in Redis using the same API."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[datetime]] = {}
        self._state: dict[str, State] = {}
        self._opened_at: dict[str, datetime] = {}
        self._half_open_inflight: dict[str, bool] = {}

    # ---------- public API ----------
    def state(self, vendor: str) -> State:
        return self._compute_state(vendor)

    def can_call(self, vendor: str) -> bool:
        st = self._compute_state(vendor)
        if st == "closed":
            return True
        if st == "open":
            return False
        # half_open: allow only one probe at a time
        if not self._half_open_inflight.get(vendor):
            self._half_open_inflight[vendor] = True
            return True
        return False

    def record_success(self, vendor: str) -> None:
        self._failures[vendor] = deque()
        self._state[vendor] = "closed"
        self._opened_at.pop(vendor, None)
        self._half_open_inflight[vendor] = False

    def record_failure(self, vendor: str) -> None:
        now = _utcnow()
        q = self._failures.setdefault(vendor, deque())
        q.append(now)
        self._purge(q)
        self._half_open_inflight[vendor] = False
        if len(q) >= THRESHOLD:
            self._state[vendor] = "open"
            self._opened_at[vendor] = now

    def info(self) -> list[dict]:
        out = []
        for vendor, q in self._failures.items():
            self._purge(q)
            out.append({
                "vendor": vendor,
                "state": self._compute_state(vendor),
                "failures_in_window": len(q),
                "threshold": THRESHOLD,
                "window_sec": WINDOW_SEC,
                "cooldown_sec": COOLDOWN_SEC,
                "opened_at": self._opened_at.get(vendor).isoformat() if self._opened_at.get(vendor) else None,
            })
        return out

    def reset(self, vendor: str) -> None:
        self._failures.pop(vendor, None)
        self._state[vendor] = "closed"
        self._opened_at.pop(vendor, None)
        self._half_open_inflight.pop(vendor, None)

    # ---------- internals ----------
    def _purge(self, q: deque[datetime]) -> None:
        cutoff = _utcnow() - timedelta(seconds=WINDOW_SEC)
        while q and q[0] < cutoff:
            q.popleft()

    def _compute_state(self, vendor: str) -> State:
        st = self._state.get(vendor, "closed")
        if st == "open":
            opened = self._opened_at.get(vendor)
            if opened and (_utcnow() - opened).total_seconds() >= COOLDOWN_SEC:
                self._state[vendor] = "half_open"
                self._half_open_inflight[vendor] = False
                return "half_open"
        return st


breaker = CircuitBreaker()
