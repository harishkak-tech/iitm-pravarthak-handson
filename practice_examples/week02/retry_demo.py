"""retry_demo.py — Week 2 practice: Pattern 3, retry with exponential backoff.
    python practice_examples/week02/retry_demo.py
"""
import asyncio
import random
import time


async def flaky():
    if random.random() < 0.7:                 # fails 70% of the time
        raise RuntimeError("transient failure")
    return "success!"


async def with_retry(tries=4):
    for attempt in range(tries):
        try:
            return await flaky()
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = 2 ** attempt               # 1, 2, 4 seconds
            print(f"[{time.strftime('%H:%M:%S')}] attempt {attempt + 1} failed — waiting {wait}s")
            await asyncio.sleep(wait)


print(asyncio.run(with_retry()))
