import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from common import enqueue, GROUP_ID
from config import build_graphiti

mcp = FastMCP("graphiti-memory")

_graphiti = None


def _g():
    global _graphiti
    if _graphiti is None:
        _graphiti = build_graphiti()
    return _graphiti


@mcp.tool()
def remember(fact: str) -> str:
    """Store a durable fact about the user into long-term memory.

    Use for stable, worth-remembering facts (preferences, decisions, who/what
    matters). It is queued and ingested in the background, so it becomes
    searchable within seconds-to-minutes, not instantly.
    """
    enqueue([{
        "session_id": "mcp",
        "speaker": os.environ.get("USER_NAME", "user"),
        "text": fact,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uuid": f"mcp-{uuid.uuid4().hex[:12]}",
        "group_id": GROUP_ID,
    }])
    return f"Queued for memory: {fact}"


@mcp.tool()
async def search_memory(query: str) -> str:
    """Search long-term memory for facts relevant to a query.

    Hybrid semantic + keyword + graph search over past conversations. Returns
    facts, newest-relevant first; expired (superseded) facts are marked.
    """
    results = await _g().search(query)
    if not results:
        return "(no matching facts in memory)"
    lines = []
    for r in results[:10]:
        expired = " [EXPIRED]" if getattr(r, "invalid_at", None) else ""
        when = getattr(r, "valid_at", None)
        lines.append(f"- {r.fact}{expired}" + (f" ({when})" if when else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
