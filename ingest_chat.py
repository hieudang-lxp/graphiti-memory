import asyncio
import json
import sys
from datetime import datetime, timezone

from graphiti_core.nodes import EpisodeType

from config import build_graphiti


def parse_ts(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def ingest(path: str, group_id: str = "chat"):
    with open(path) as f:
        messages = json.load(f)

    g = build_graphiti()
    await g.build_indices_and_constraints()

    for i, m in enumerate(messages):
        speaker = m.get("speaker", "unknown")
        text = m["text"]
        ts = parse_ts(m["timestamp"]) if m.get("timestamp") else datetime.now(timezone.utc)
        print(f">> [{i + 1}/{len(messages)}] {speaker} @ {ts.isoformat()}")
        await g.add_episode(
            name=f"{group_id}-msg-{i + 1}",
            episode_body=f"{speaker}: {text}",
            source=EpisodeType.message,
            source_description=f"chat:{group_id}",
            reference_time=ts,
            group_id=group_id,
        )

    async with g.driver.session() as s:
        n = (await (await s.run("MATCH (n:Entity) RETURN count(n) AS c")).single())["c"]
        r = (await (await s.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS c")).single())["c"]
    await g.close()
    print(f"\nDONE. Graph now: {n} entities, {r} relationships.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python ingest_chat.py <chat.json> [group_id]")
        sys.exit(1)
    gid = sys.argv[2] if len(sys.argv) > 2 else "chat"
    asyncio.run(ingest(sys.argv[1], gid))
