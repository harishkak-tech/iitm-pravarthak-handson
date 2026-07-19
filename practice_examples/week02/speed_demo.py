"""speed_demo.py — Week 2 practice: the async payoff (sync vs parallel). Standalone.
    python practice_examples/week02/speed_demo.py
"""
import asyncio
import random
import time


async def fake_llm_call(prompt: str) -> str:
    await asyncio.sleep(random.uniform(0.3, 1.5))    # pretend network wait
    return f"answer to: {prompt}"


QUESTIONS = [f"question {i}" for i in range(10)]


async def sequential():
    for q in QUESTIONS:
        await fake_llm_call(q)                       # one at a time


async def parallel():
    await asyncio.gather(*(fake_llm_call(q) for q in QUESTIONS))   # all at once


for label, coro in [("sequential (one-at-a-time)", sequential),
                    ("parallel  (asyncio.gather)", parallel)]:
    start = time.time()
    asyncio.run(coro())
    print(f"{label:26} {time.time() - start:5.1f}s  for {len(QUESTIONS)} calls")
