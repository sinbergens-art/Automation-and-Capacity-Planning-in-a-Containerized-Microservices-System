from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from typing import Iterable

try:
    import httpx
except ImportError: 
    print("Need httpx. Install with:  pip install httpx", file=sys.stderr)
    sys.exit(1)


def scenario_mixed(base: str) -> list[tuple[str, str, dict | None]]:
    """A read-heavy mix that exercises multiple services (the typical
    e-commerce browsing pattern)."""
    return [
        ("GET", f"{base}/products",        None),
        ("GET", f"{base}/products/1",      None),
        ("GET", f"{base}/products/2",      None),
        ("GET", f"{base}/orders",          None),
        ("GET", f"{base}/users/demo1",     None),
    ]


def scenario_orders(base: str) -> list[tuple[str, str, dict | None]]:
    """Write-heavy scenario against the most resource-intensive service."""
    return [
        ("GET",  f"{base}/products",   None),
        ("POST", f"{base}/orders",     {
            "username": f"loaduser-{random.randint(1, 999)}",
            "items":   [{"product_id": random.randint(1, 5), "quantity": random.randint(1, 3)}],
        }),
    ]


def scenario_health(base: str) -> list[tuple[str, str, dict | None]]:
    """Smoke test - just /health endpoints. Fast, low resource usage."""
    return [
        ("GET", f"{base.replace(':80', ':8001')}/health", None),
        ("GET", f"{base.replace(':80', ':8002')}/health", None),
        ("GET", f"{base.replace(':80', ':8003')}/health", None),
        ("GET", f"{base.replace(':80', ':8004')}/health", None),
        ("GET", f"{base.replace(':80', ':8005')}/health", None),
    ]


SCENARIOS = {
    "mixed":  scenario_mixed,
    "orders": scenario_orders,
    "health": scenario_health,
}

class Stats:
    def __init__(self) -> None:
        self.start = time.perf_counter()
        self.latencies: list[float] = []
        self.statuses: Counter[int] = Counter()
        self.errors  : Counter[str] = Counter()
        self.per_path: dict[str, list[float]] = defaultdict(list)

    def record(self, status: int, latency_ms: float, path: str) -> None:
        self.latencies.append(latency_ms)
        self.statuses[status] += 1
        self.per_path[path].append(latency_ms)

    def record_error(self, kind: str) -> None:
        self.errors[kind] += 1

    def report(self) -> None:
        elapsed = time.perf_counter() - self.start
        total = sum(self.statuses.values()) + sum(self.errors.values())
        ok = sum(c for s, c in self.statuses.items() if 200 <= s < 400)
        bad = total - ok
        print()
        print("=" * 70)
        print("Load test summary")
        print("=" * 70)
        print(f"  Duration:        {elapsed:6.2f} s")
        print(f"  Total requests:  {total}")
        print(f"  Throughput:      {total / max(elapsed, 1e-9):8.2f} req/s")
        print(f"  Success (2xx):   {ok}  ({ok / max(total, 1) * 100:5.1f} %)")
        print(f"  Failures:        {bad}")
        if self.latencies:
            p50 = statistics.median(self.latencies)
            p95 = statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else max(self.latencies)
            p99 = statistics.quantiles(self.latencies, n=100)[98] if len(self.latencies) >= 100 else max(self.latencies)
            print(f"  Latency p50:     {p50:6.1f} ms")
            print(f"  Latency p95:     {p95:6.1f} ms")
            print(f"  Latency p99:     {p99:6.1f} ms")
        print()
        print("HTTP status breakdown:")
        for status, count in sorted(self.statuses.items()):
            print(f"  {status}: {count}")
        if self.errors:
            print()
            print("Errors:")
            for err, count in self.errors.most_common():
                print(f"  {err}: {count}")
        print()
        print("Per-endpoint latency (avg ms / count):")
        for path, lats in self.per_path.items():
            avg = sum(lats) / len(lats)
            print(f"  {avg:6.1f}  {len(lats):4d}  {path}")

async def worker(
    client: httpx.AsyncClient,
    requests: Iterable[tuple[str, str, dict | None]],
    deadline: float,
    stats: Stats,
) -> None:
    requests = list(requests)
    while time.perf_counter() < deadline:
        method, url, body = random.choice(requests)
        t0 = time.perf_counter()
        try:
            r = await client.request(method, url, json=body, timeout=10.0)
            stats.record(r.status_code, (time.perf_counter() - t0) * 1000, _short(url))
        except httpx.TimeoutException:
            stats.record_error("timeout")
        except httpx.ConnectError as e:
            stats.record_error(f"connect:{type(e).__name__}")
        except Exception as e:
            stats.record_error(type(e).__name__)


def _short(url: str) -> str:
    return url.split("/", 3)[-1] if url.count("/") >= 3 else url


async def main() -> None:
    p = argparse.ArgumentParser(description="Capacity-planning load generator")
    p.add_argument("--base",     default="http://localhost", help="Base URL (default: http://localhost)")
    p.add_argument("--scenario", default="mixed", choices=SCENARIOS.keys())
    p.add_argument("--users",    type=int, default=20, help="Concurrent virtual users")
    p.add_argument("--duration", type=int, default=20, help="Test duration in seconds")
    args = p.parse_args()

    requests = SCENARIOS[args.scenario](args.base)
    deadline = time.perf_counter() + args.duration

    print(f"Scenario={args.scenario}  users={args.users}  duration={args.duration}s  base={args.base}")
    print(f"Endpoints: {len(requests)}")
    print("-" * 70)

    stats = Stats()
    async with httpx.AsyncClient(http2=False) as client:
        await asyncio.gather(*[
            worker(client, requests, deadline, stats) for _ in range(args.users)
        ])
    stats.report()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted.")
