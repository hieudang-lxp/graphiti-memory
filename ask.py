import asyncio
import sys

from config import build_graphiti


async def ask(query: str):
    g = build_graphiti()
    try:
        results = await g.search(query)
        if not results:
            print("(no matching facts)")
        for r in results[:10]:
            when = getattr(r, "valid_at", None)
            invalid = getattr(r, "invalid_at", None)
            tag = " [EXPIRED]" if invalid else ""
            stamp = f"  ({when})" if when else ""
            print(f"- {r.fact}{tag}{stamp}")
    finally:
        await g.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python ask.py "your question"')
        sys.exit(1)
    asyncio.run(ask(" ".join(sys.argv[1:])))
