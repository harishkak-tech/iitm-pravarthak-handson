"""gather_demo.py — Week 2 practice: Pattern 1, asyncio.gather.
    python practice_examples/week02/gather_demo.py
"""
import asyncio
import time


async def one_second_task(n):
    await asyncio.sleep(1)
    return n


async def main():
    results = await asyncio.gather(*(one_second_task(i) for i in range(10)))
    print("results (in order):", results)


start = time.time()
asyncio.run(main())
print(f"10 one-second tasks in {time.time() - start:.1f}s")     # ~1s
