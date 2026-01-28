from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass
class Histogram:
    buckets: Tuple[float, ...]
    # bucket upper bound -> cumulative count
    counts: Dict[float, int]
    sum: float
    count: int

    @classmethod
    def with_buckets(cls, buckets: Iterable[float]) -> "Histogram":
        b = tuple(sorted(set(float(x) for x in buckets)))
        if not b:
            raise ValueError("histogram buckets cannot be empty")
        counts = {ub: 0 for ub in b}
        return cls(buckets=b, counts=counts, sum=0.0, count=0)

    def observe(self, value: float) -> None:
        self.count += 1
        self.sum += value
        for ub in self.buckets:
            if value <= ub:
                self.counts[ub] += 1
        # implicit +Inf bucket = count


class Metrics:
    """Very small in-process Prometheus-style metrics.

    Note: in-memory only; resets on restart. Good enough for this evaluation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.http_requests_total: Dict[Tuple[str, int], int] = {}
        self.webhook_requests_total: Dict[str, int] = {}
        # latency in seconds
        self.request_latency = Histogram.with_buckets(
            [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )

    def inc_http(self, path: str, status: int) -> None:
        with self._lock:
            key = (path, int(status))
            self.http_requests_total[key] = self.http_requests_total.get(key, 0) + 1

    def inc_webhook(self, result: str) -> None:
        with self._lock:
            self.webhook_requests_total[result] = self.webhook_requests_total.get(result, 0) + 1

    def observe_latency(self, seconds: float) -> None:
        with self._lock:
            self.request_latency.observe(max(0.0, float(seconds)))

    def render_prometheus(self) -> str:
        with self._lock:
            lines: list[str] = []

            # http_requests_total
            lines.append("# HELP http_requests_total Total HTTP requests")
            lines.append("# TYPE http_requests_total counter")
            for (path, status), val in sorted(self.http_requests_total.items()):
                lines.append(
                    f'http_requests_total{{path="{_esc(path)}",status="{status}"}} {val}'
                )

            # webhook_requests_total
            lines.append("# HELP webhook_requests_total Webhook requests by result")
            lines.append("# TYPE webhook_requests_total counter")
            for result, val in sorted(self.webhook_requests_total.items()):
                lines.append(
                    f'webhook_requests_total{{result="{_esc(result)}"}} {val}'
                )

            # request_latency_seconds
            h = self.request_latency
            lines.append("# HELP request_latency_seconds Request latency")
            lines.append("# TYPE request_latency_seconds histogram")
            cum = 0
            for ub in h.buckets:
                cum = h.counts.get(ub, cum)
                lines.append(
                    f'request_latency_seconds_bucket{{le="{ub}"}} {cum}'
                )
            lines.append(f'request_latency_seconds_bucket{{le="+Inf"}} {h.count}')
            lines.append(f"request_latency_seconds_sum {h.sum}")
            lines.append(f"request_latency_seconds_count {h.count}")

            return "\n".join(lines) + "\n"


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def now_monotonic() -> float:
    return time.monotonic()
