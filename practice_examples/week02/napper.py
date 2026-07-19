"""napper.py — Week 2 practice: asyncio.gather fires many tasks at once.
    python practice_examples/week02/napper.py
"""
import asyncio
import time


async def nap(name, seconds):
    print(f"{name} start")
    await asyncio.sleep(seconds)
    print(f"{name} done after {seconds}s")
    return name


async def main():
    results = await asyncio.gather(nap("A", 1), nap("B", 2), nap("C", 3))
    print("results (in order):", results)


start = time.time()
asyncio.run(main())
print(f"total: {time.time() - start:.1f}s")     # ~3s (the max), not 6s (the sum)
