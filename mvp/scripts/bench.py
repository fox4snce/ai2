import asyncio
import json
import time
from statistics import median
from typing import List

import psutil
import httpx


BASE = "http://127.0.0.1:8000"


def make_cases(n: int) -> List[dict]:
    cases = []
    for i in range(n):
        if i % 5 == 0:
            # logic
            cases.append({
                "obligations": [{
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "domains": ["kinship"],
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                        "facts": [
                            {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                        ],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }]})
        elif i % 5 == 1:
            # plan clarify
            cases.append({
                "obligations": [{
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "mode": "planning",
                        "goal": {"predicate": "event.scheduled", "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}},
                        "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                    }
                }]})
        elif i % 5 == 2:
            # truncated
            cases.append({
                "obligations": [{
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "domains": ["kinship"],
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                        "facts": [
                            {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                        ],
                        "budgets": {"max_depth": 1, "beam": 4, "time_ms": 100}
                    }
                }]})
        elif i % 5 == 3:
            # guardrail fail
            cases.append({
                "obligations": [{
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "mode": "planning",
                        "goal": {"predicate": "event.scheduled", "args": {"person": "Alice", "time": "2025-09-08T10:00Z"}},
                        "guardrails": [
                            {"predicate": "calendar.free", "args": ["Alice", {"start": "2025-09-08T09:00Z", "end": "2025-09-08T17:00Z"}]}
                        ],
                        "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                    }
                }]})
        else:
            # people query
            cases.append({
                "obligations": [{
                    "type": "REPORT",
                    "payload": {
                        "kind": "query.people",
                        "filters": [{"city": "Seattle"}]
                    }
                }]})
    return cases


async def run_case(client: httpx.AsyncClient, payload: dict) -> float:
    t0 = time.time()
    r = await client.post(BASE + "/v1/obligations/execute", json=payload)
    r.raise_for_status()
    _ = r.json()
    return (time.time() - t0) * 1000.0


async def main(concurrency: int = 32, total: int = 64):
    cases = make_cases(total)
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        tasks = [run_case(client, p) for p in cases]
        results = []
        for i in range(0, len(tasks), concurrency):
            chunk = tasks[i:i+concurrency]
            results.extend(await asyncio.gather(*chunk))
    p50 = median(results)
    p95 = sorted(results)[int(0.95 * len(results)) - 1]
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory().percent
    bench = {"p50_ms": p50, "p95_ms": p95, "req_s": len(results) / (sum(results) / 1000.0), "cpu_percent": cpu, "mem_percent": mem}
    print(json.dumps(bench, indent=2))
    with open("bench.json", "w") as f:
        json.dump(bench, f)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--total", type=int, default=64)
    args = ap.parse_args()
    asyncio.run(main(args.concurrency, args.total))


