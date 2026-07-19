"""batch_demo.py — Week 2 practice: Pattern 2, batching (paced chunks).
    python practice_examples/week02/batch_demo.py
"""
import asyncio
import time


async def work(n):
    await asyncio.sleep(0.5)
    return n


async def run_in_batches(items, batch_size):
    out = []
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        print(f"batch {i // batch_size + 1}: {len(chunk)} items")
        out.extend(await asyncio.gather(*(work(x) for x in chunk)))
        await asyncio.sleep(0.1)          # the polite pause between batches
    return out


start = time.time()
asyncio.run(run_in_batches(list(range(12)), batch_size=5))
print(f"done in {time.time() - start:.1f}s")
