import asyncio
from datetime import datetime, timezone

from graphiti_core.nodes import EpisodeType

from config import build_graphiti

EPISODES = [
    "Alex is a software engineer at Acme. They lead the internal AI tooling initiative.",
    "Acme's frontend is organized into shared packages like the design-system and "
    "common-utils, used across several product repos.",
    "Alex set up a local Ollama stack running Qwen2.5 models to keep everything on-device.",
    "The AI tooling initiative aims to apply spec-driven development, borrowing "
    "patterns from the backend repos.",
    "Alex is building a personal memory system using Graphiti and Neo4j on their laptop.",
]


async def main():
    g = build_graphiti()
    print(">> building indices/constraints ...")
    await g.build_indices_and_constraints()

    now = datetime.now(timezone.utc)
    for i, body in enumerate(EPISODES):
        print(f">> ingesting episode {i + 1}/{len(EPISODES)} ...")
        await g.add_episode(
            name=f"episode-{i + 1}",
            episode_body=body,
            source=EpisodeType.text,
            source_description="smoke test",
            reference_time=now,
        )

    print("\n===== GRAPH INSPECTION (Cypher) =====")
    driver = g.driver
    async with driver.session() as s:
        entities = await (await s.run(
            "MATCH (n:Entity) RETURN n.name AS name ORDER BY name"
        )).values()
        rels = await (await s.run(
            "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
            "RETURN a.name AS src, r.fact AS fact, b.name AS dst LIMIT 40"
        )).values()

    print(f"\nENTITIES ({len(entities)}):")
    for (name,) in entities:
        print(f"  - {name}")

    print(f"\nRELATIONSHIPS ({len(rels)}):")
    for src, fact, dst in rels:
        print(f"  ({src}) -[{fact}]-> ({dst})")

    print("\n===== SEARCH: 'What is Alex working on?' =====")
    try:
        results = await g.search("What is Alex working on?")
        for r in results[:5]:
            print(f"  FACT: {r.fact}")
    except Exception as e:
        print(f"  (search/rerank failed, not fatal for the gate: {e})")

    await g.close()

    print("\n===== VERDICT =====")
    if len(entities) >= 4 and len(rels) >= 2:
        print("GO: graph looks coherent. Safe to scale ingestion.")
    else:
        print("NO-GO: sparse/empty graph. Try a larger model.")


if __name__ == "__main__":
    asyncio.run(main())
