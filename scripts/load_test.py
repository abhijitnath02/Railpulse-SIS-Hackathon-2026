"""
Item 11 — Load test the API.

Hits a REAL running server (default http://localhost:8000) with concurrent
requests and reports p50/p95/p99 latency and achieved throughput. This is
a genuine load test, not a simulation: it needs `uvicorn backend.main:app`
(or equivalent) actually running first.

Usage:
    # Terminal 1
    uvicorn backend.main:app --port 8000

    # Terminal 2
    python scripts/load_test.py --endpoint /trains --concurrency 20 --total-requests 500
    python scripts/load_test.py --endpoint "/eta/predict?train_no=<X>&current_station_code=<A>&next_station_code=<B>" \
        --concurrency 20 --total-requests 500

Run `python -c "import json,requests; print(json.dumps(requests.get('http://localhost:8000/trains').json()[0], indent=2))"`
first if you need real train_no/station_code values for the /eta/predict case.

REQUIRES: httpx (see requirements.txt). Not executed in the assistant's
sandbox — no fastapi/uvicorn installed there and no network access to
install them. Run this against your own local server and treat its
printed numbers as the real result; nothing here is pre-filled or assumed.
"""
import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import List

import httpx


@dataclass
class LoadTestResult:
    latencies_ms: List[float] = field(default_factory=list)
    status_codes: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    wall_clock_seconds: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for c in self.status_codes if 200 <= c < 300)

    @property
    def error_count(self) -> int:
        return len(self.status_codes) - self.success_count + len(self.errors)

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return float("nan")
        s = sorted(self.latencies_ms)
        k = (len(s) - 1) * (p / 100)
        f, c = int(k), min(int(k) + 1, len(s) - 1)
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)


async def _worker(client: httpx.AsyncClient, url: str, method: str, json_body, result: LoadTestResult, headers: dict):
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        else:
            resp = await client.post(url, json=json_body, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000
        result.latencies_ms.append(elapsed_ms)
        result.status_codes.append(resp.status_code)
    except Exception as exc:  # noqa: BLE001 — record any transport-level failure
        elapsed_ms = (time.perf_counter() - start) * 1000
        result.latencies_ms.append(elapsed_ms)
        result.errors.append(str(exc))


async def run_load_test(base_url: str, endpoint: str, method: str, json_body, concurrency: int, total_requests: int, headers: dict) -> LoadTestResult:
    url = f"{base_url}{endpoint}"
    result = LoadTestResult()
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_worker(client):
        async with semaphore:
            await _worker(client, url, method, json_body, result, headers)

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        await asyncio.gather(*(bounded_worker(client) for _ in range(total_requests)))
    result.wall_clock_seconds = time.perf_counter() - start
    return result


def print_report(result: LoadTestResult, total_requests: int, concurrency: int, endpoint: str):
    print("=" * 60)
    print(f"Load test report — {endpoint}")
    print("=" * 60)
    print(f"Requests:        {total_requests} (concurrency {concurrency})")
    print(f"Wall clock:      {result.wall_clock_seconds:.2f}s")
    if result.wall_clock_seconds > 0:
        print(f"Throughput:      {total_requests / result.wall_clock_seconds:.1f} req/s")
    print(f"Success:         {result.success_count}/{total_requests}")
    print(f"Errors:          {result.error_count}")
    if result.latencies_ms:
        print(f"Latency p50:     {result.percentile(50):.1f} ms")
        print(f"Latency p95:     {result.percentile(95):.1f} ms")
        print(f"Latency p99:     {result.percentile(99):.1f} ms")
        print(f"Latency mean:    {statistics.mean(result.latencies_ms):.1f} ms")
        print(f"Latency max:     {max(result.latencies_ms):.1f} ms")
    if result.errors:
        print(f"\nSample errors (up to 5): {result.errors[:5]}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Load test the RailPulse API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--endpoint", default="/trains", help="Path (with query string) to hit")
    parser.add_argument("--method", default="GET", choices=["GET", "POST"])
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--total-requests", type=int, default=500)
    parser.add_argument("--username", default=None, help="If set (with --password), logs in first and sends the token as a Bearer header on every request -- required now that most endpoints need auth.")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    headers = {}
    if args.username and args.password:
        import httpx as _httpx
        resp = _httpx.post(f"{args.base_url}/auth/token", data={"username": args.username, "password": args.password})
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers["Authorization"] = f"Bearer {token}"
        print(f"Logged in as {args.username}, using token on every request.")

    result = asyncio.run(run_load_test(
        args.base_url, args.endpoint, args.method, None, args.concurrency, args.total_requests, headers,
    ))
    print_report(result, args.total_requests, args.concurrency, args.endpoint)


if __name__ == "__main__":
    main()
