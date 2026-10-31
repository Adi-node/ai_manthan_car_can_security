import time
from collections import deque
from typing import Optional

import numpy as np


class Stats:
    def __init__(self, latency_window: int = 5000):
        self.start = time.monotonic()
        self.latencies: deque[float] = deque(maxlen=latency_window)
        self.recent: deque[float] = deque(maxlen=2000)  # arrival times, for throughput
        self.processed = 0
        self.confusion = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    def record(self, inference_ms: float, is_attack: bool, label: Optional[int]) -> None:
        self.processed += 1
        self.latencies.append(inference_ms)
        self.recent.append(time.monotonic())
        if label is not None:
            key = ("t" if is_attack == bool(label) else "f") + ("p" if is_attack else "n")
            self.confusion[key] += 1

    def _throughput(self) -> float:
        now = time.monotonic()
        n = sum(1 for t in self.recent if now - t <= 1.0)
        return float(n)

    def snapshot(self, dashboard_clients: int) -> dict:
        if self.latencies:
            a = np.fromiter(self.latencies, dtype=np.float64)
            p50, p95, p99 = np.percentile(a, [50, 95, 99])
            lat = {"p50": round(float(p50), 4), "p95": round(float(p95), 4),
                   "p99": round(float(p99), 4), "max": round(float(a.max()), 4)}
        else:
            lat = {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        return {
            "uptime_s": round(time.monotonic() - self.start, 1),
            "windows_processed": self.processed,
            "throughput_wps": self._throughput(),
            "inference_ms": lat,
            "confusion": dict(self.confusion),
            "dashboard_clients": dashboard_clients,
        }
