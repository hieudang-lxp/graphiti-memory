import json
import sys

from neo4j import GraphDatabase

sys.path.insert(0, __file__.rsplit("/", 2)[0])
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

RECENT_Q = """
MATCH ()-[r:RELATES_TO]->()
WHERE r.expired_at IS NULL AND r.invalid_at IS NULL AND r.fact IS NOT NULL
RETURN r.fact AS fact
ORDER BY coalesce(r.valid_at, r.created_at) DESC
LIMIT 20
"""

KEY_ENTITY_Q = """
MATCH (n:Entity)
WITH n, COUNT { (n)-[:RELATES_TO]-() } AS deg
WHERE deg > 0
RETURN n.name AS name, deg
ORDER BY deg DESC
LIMIT 8
"""


def build_digest() -> str:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as s:
            recent = [r["fact"] for r in s.run(RECENT_Q)]
            keys = [(r["name"], r["deg"]) for r in s.run(KEY_ENTITY_Q)]
    finally:
        driver.close()

    if not recent and not keys:
        return ""

    lines = ["# Memory — what I know about you from past sessions (Graphiti)"]
    if keys:
        lines.append("\nKey things: " + ", ".join(f"{n} ({d})" for n, d in keys))
    if recent:
        lines.append("\nRecent still-valid facts:")
        lines += [f"- {f}" for f in recent]
    lines.append(
        "\n(This is long-term memory from prior conversations. Treat as background; "
        "verify against the current repo before asserting as fact.)"
    )
    return "\n".join(lines)


def main():
    try:
        digest = build_digest()
    except Exception:  # noqa: BLE001
        return
    if not digest:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": digest,
        }
    }))


if __name__ == "__main__":
    main()
