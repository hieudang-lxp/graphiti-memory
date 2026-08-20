import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graphiti_core.nodes import EpisodeType

from common import QUEUE_FILE, WORKER_OFFSET, WORKER_LOG
from config import build_graphiti

POLL_SECONDS = 5


def log(msg: str):
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    with open(WORKER_LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def read_offset() -> int:
    try:
        with open(WORKER_OFFSET) as f:
            return int(f.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def write_offset(n: int):
    tmp = WORKER_OFFSET + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(n))
    os.replace(tmp, WORKER_OFFSET)


def parse_ts(raw):
    if not raw:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def ingest_one(g, rec: dict):
    speaker = rec.get("speaker", "unknown")
    text = rec["text"]
    ts = parse_ts(rec.get("timestamp"))
    name = f"{rec.get('session_id', 'sess')}-{rec.get('uuid', 'msg')}"
    await g.add_episode(
        name=name,
        episode_body=f"{speaker}: {text}",
        source=EpisodeType.message,
        source_description="claude-chat",
        reference_time=ts,
        group_id=rec.get("group_id", "personal"),
    )


async def main():
    log("worker starting")
    g = build_graphiti()
    await g.build_indices_and_constraints()
    log("graphiti ready, entering poll loop")
    try:
        while True:
            if os.path.exists(QUEUE_FILE):
                with open(QUEUE_FILE) as f:
                    lines = f.readlines()
                offset = read_offset()
                for i in range(offset, len(lines)):
                    raw = lines[i].strip()
                    if not raw:
                        write_offset(i + 1)
                        continue
                    try:
                        rec = json.loads(raw)
                    except json.JSONDecodeError:
                        break
                    try:
                        await ingest_one(g, rec)
                        log(f"ingested #{i} {rec.get('speaker')}: {rec.get('text', '')[:60]!r}")
                    except Exception as e:  # noqa: BLE001
                        log(f"ERROR on #{i}: {e!r} — skipping")
                    write_offset(i + 1)
            await asyncio.sleep(POLL_SECONDS)
    finally:
        await g.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
