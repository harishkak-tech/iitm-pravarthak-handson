"""scripts/stress_test.py — concurrent stress test for /ask.

Sends N parallel POST requests through your FastAPI service and reports
timing + any errors. Used in Lab Step 3 sub-step 3d.

Usage:
    python scripts/stress_test.py --requests 50 --concurrent 10
"""
import argparse
import asyncio
import time

import httpx


CAPSTONE_QUESTIONS = [
    "What is the leave policy?",
    "How does the procurement approval process work?",
    "Who do I contact for tech support?",
    "What is the parental leave policy?",
    "How do I file a reimbursement claim?",
    "What is the WFH policy this quarter?",
    "Who approves a new vendor?",
    "What is the IT helpdesk number?",
]


async def ask_one(client: httpx.AsyncClient, question: str, idx: int) -> dict:
    start = time.time()
    try:
        response = await client.post(
            "http://localhost:8000/ask",
            json={"question": question},
            timeout=60.0,
        )
        _body = await response.aread()
        return {
            "idx": idx,
            "status": response.status_code,
            "elapsed": time.time() - start,
            "bytes": len(_body),
        }
    except Exception as e:
        return {
            "idx": idx,
            "status": "ERR",
            "error": f"{type(e).__name__}: {e}",
            "elapsed": time.time() - start,
        }


async def main(n_requests: int, concurrent: int):
    sem = asyncio.Semaphore(concurrent)

    async def bounded(client, q, i):
        async with sem:
            return await ask_one(client, q, i)

    print(f"Stress test: {n_requests} requests, up to {concurrent} concurrent")
    print("─" * 60)

    async with httpx.AsyncClient() as client:
        tasks = [
            bounded(client, CAPSTONE_QUESTIONS[i % len(CAPSTONE_QUESTIONS)], i)
            for i in range(n_requests)
        ]
        start = time.time()
        results = await asyncio.gather(*tasks)
        total = time.time() - start

    successes = [r for r in results if r.get("status") == 200]
    failures = [r for r in results if r.get("status") != 200]

    print(f"Total wall time:   {total:.2f}s")
    print(f"Successes:         {len(successes)} / {n_requests}")
    print(f"Effective req/s:   {n_requests / total:.2f}")

    if successes:
        elapsed = sorted(r["elapsed"] for r in successes)
        n = len(elapsed)
        print()
        print("Latency (successful requests):")
        print(f"  min:   {elapsed[0]:.2f}s")
        print(f"  p50:   {elapsed[n // 2]:.2f}s")
        print(f"  p95:   {elapsed[int(n * 0.95)]:.2f}s")
        print(f"  max:   {elapsed[-1]:.2f}s")

    if failures:
        print()
        print(f"Failures ({len(failures)}):")
        for f in failures[:5]:
            print(f"  idx={f['idx']}  {f.get('error', f.get('status'))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrent", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(main(args.requests, args.concurrent))
