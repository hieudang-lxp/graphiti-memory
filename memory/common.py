import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(BASE, "memory")
QUEUE_FILE = os.path.join(MEM, "queue.jsonl")
STATE_FILE = os.path.join(MEM, "state.json")
WORKER_OFFSET = os.path.join(MEM, "worker.offset")
WORKER_LOG = os.path.join(MEM, "worker.log")

load_dotenv(os.path.join(BASE, ".env"))

USER_NAME = os.environ.get("USER_NAME", "user")
GROUP_ID = os.environ.get("GROUP_ID", "personal")
INGEST_ASSISTANT = os.environ.get("INGEST_ASSISTANT", "0") == "1"

_INJECTED_MARKERS = (
    "<task-notification>",
    "[SYSTEM NOTIFICATION",
    "<system-reminder>",
    "caveat:",
    "<command-",
    "<local-command",
    "<user-memory-input>",
    "Base directory for this skill:",
    "Caveat:",
    "<user-prompt-submit-hook>",
)
_TRIVIAL = {"ok", "okay", "thanks", "thank you", "ty", "cool", "nice", "done", "yes", "no"}


def is_real_user_text(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if any(t.startswith(m) for m in _INJECTED_MARKERS):
        return False
    return True


def is_substantive(text: str) -> bool:
    t = text.strip()
    return len(t) >= 8 and t.lower() not in _TRIVIAL


def extract_messages(transcript_path: str, start_line: int):
    if not os.path.exists(transcript_path):
        return
    with open(transcript_path) as f:
        for idx, line in enumerate(f):
            if idx < start_line:
                continue
            line = line.strip()
            if not line:
                yield idx, None
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                yield idx, None
                continue
            yield idx, _parse_record(d)


def _parse_record(d: dict):
    typ = d.get("type")
    if typ not in ("user", "assistant"):
        return None
    msg = d.get("message", {}) or {}
    content = msg.get("content")
    ts = d.get("timestamp")
    uuid = d.get("uuid")

    if typ == "user":
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        else:
            return None
        if not is_real_user_text(text) or not is_substantive(text):
            return None
        return {"speaker": USER_NAME, "text": text.strip(), "timestamp": ts, "uuid": uuid}

    if not INGEST_ASSISTANT:
        return None
    if isinstance(content, list):
        text = " ".join(
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ).strip()
    elif isinstance(content, str):
        text = content.strip()
    else:
        return None
    if not is_substantive(text):
        return None
    return {"speaker": "Claude", "text": text, "timestamp": ts, "uuid": uuid}


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def enqueue(records):
    os.makedirs(MEM, exist_ok=True)
    with open(QUEUE_FILE, "a") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
