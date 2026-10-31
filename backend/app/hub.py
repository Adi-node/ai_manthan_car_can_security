import asyncio
import json
import time
from typing import Any, Optional

from .failsafe import Decision
from .schemas import SCHEMA_VERSION
from .stats import Stats

ATTACK_SEQS_CAP = 50


def _new_interval() -> dict[str, Any]:
    return {"windows": 0, "attack_windows": 0, "max_attack_probability": 0.0,
            "max_inference_ms": 0.0, "attack_seqs": []}


class DashboardHub:
    """Fan-out to dashboards, capped at `rate_hz` frames/s per client.

    Inference never waits on this: publish() only updates in-memory aggregates, and run()
    flushes them once per tick. Each client queue holds one frame (latest wins).
    """

    def __init__(self, stats: Stats, rate_hz: float = 30.0, hold_s: float = 2.0):
        self.stats = stats
        self.period = 1.0 / rate_hz
        self.hold_s = hold_s
        self.queues: dict[Any, asyncio.Queue] = {}
        self._interval = _new_interval()
        self._latest: Optional[dict] = None
        self._dirty = False
        self._fs: dict[str, Any] = {"seq": None, "reason": None, "t": None}
        self._streak = 0
        self.frames_sent = 0

    def add(self, ws) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self.queues[ws] = q
        return q

    def remove(self, ws) -> None:
        self.queues.pop(ws, None)

    def publish(self, latest: dict, decision: Decision) -> None:
        iv = self._interval
        pred = latest["prediction"]
        iv["windows"] += 1
        iv["max_attack_probability"] = max(iv["max_attack_probability"], pred["attack_probability"])
        iv["max_inference_ms"] = max(iv["max_inference_ms"], latest["latency"]["inference_ms"])
        if pred["is_attack"]:
            iv["attack_windows"] += 1
            if len(iv["attack_seqs"]) < ATTACK_SEQS_CAP:
                iv["attack_seqs"].append(latest["seq"])
        self._streak = decision.consecutive_attack_windows
        if decision.triggered:  # latched: survives until the hold expires, even if the trigger fell mid-interval
            self._fs = {"seq": latest["seq"], "reason": decision.reason, "t": time.monotonic()}
        self._latest = latest
        self._dirty = True

    def _failsafe_block(self) -> dict:
        t = self._fs["t"]
        active = t is not None and (time.monotonic() - t) < self.hold_s
        return {"triggered": active, "triggered_at_seq": self._fs["seq"],
                "consecutive_attack_windows": self._streak,
                "reason": self._fs["reason"] if active else None}

    async def run(self) -> None:
        last_stats = 0.0
        next_tick = time.monotonic()
        while True:
            next_tick += self.period
            await asyncio.sleep(max(0.0, next_tick - time.monotonic()))
            now = time.monotonic()
            stats_due = now - last_stats >= 1.0
            if self._latest is None or not (self._dirty or stats_due) or not self.queues:
                if self._latest is not None and not self.queues:
                    self._interval, self._dirty = _new_interval(), False
                continue
            frame = {
                "type": "dashboard_frame",
                "schema_version": SCHEMA_VERSION,
                "server_ts_ns": time.time_ns(),
                "interval": self._interval,
                "failsafe": self._failsafe_block(),
                "latest": self._latest,
                "stats": None,
            }
            if stats_due:
                frame["stats"] = self.stats.snapshot(len(self.queues))
                last_stats = now
            self._interval, self._dirty = _new_interval(), False
            payload = json.dumps(frame)
            for q in self.queues.values():
                if q.full():
                    q.get_nowait()
                q.put_nowait(payload)
            self.frames_sent += 1
