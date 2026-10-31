#!/usr/bin/env python3
"""Compare p50/p95 latency with cache on vs off."""

from __future__ import annotations

import argparse
import statistics
import time

import httpx


QUESTIONS = [
    "What is Hit@k in retrieval evaluation?",
    "What is TTFT?",
    "How does semantic cache decide to reuse an answer?",
    "What commonly drives haze in Singapore?",
    "Why include prompt version in cache keys?",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[idx]


def run_pass(client: httpx.Client, base_url: str, use_cache: bool, rounds: int) -> list[float]:
    latencies: list[float] = []
    for _ in range(rounds):
        for q in QUESTIONS:
            start = time.perf_counter()
            resp = client.post(
                f"{base_url}/ask",
                json={"question": q, "use_cache": use_cache},
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            # Prefer server e2e timing
            latencies.append(float(data["timings"]["e2e_ms"]))
            _ = time.perf_counter() - start
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--rounds", type=int, default=2, help="Passes over the question list")
    args = parser.parse_args()

    with httpx.Client() as client:
        print("Warm-up (cache off)...")
        run_pass(client, args.base_url, use_cache=False, rounds=1)

        print("Benchmark cache OFF...")
        off = run_pass(client, args.base_url, use_cache=False, rounds=args.rounds)

        print("Prime cache...")
        run_pass(client, args.base_url, use_cache=True, rounds=1)

        print("Benchmark cache ON...")
        on = run_pass(client, args.base_url, use_cache=True, rounds=args.rounds)

    def report(name: str, values: list[float]) -> None:
        print(
            f"{name}: n={len(values)} mean={statistics.mean(values):.1f}ms "
            f"p50={percentile(values, 50):.1f}ms p95={percentile(values, 95):.1f}ms"
        )

    report("cache_off", off)
    report("cache_on", on)
    if off and on:
        print(f"p95 speedup: {percentile(off, 95) / max(percentile(on, 95), 1e-6):.2f}x")


if __name__ == "__main__":
    main()
