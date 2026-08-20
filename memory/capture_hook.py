import json
import sys

from common import extract_messages, enqueue, load_json, save_json, STATE_FILE, GROUP_ID


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    session_id = payload.get("session_id") or "unknown"
    transcript = payload.get("transcript_path")
    if not transcript:
        return

    state = load_json(STATE_FILE, {})
    start = state.get(session_id, 0)

    records = []
    last_idx = start - 1
    for idx, msg in extract_messages(transcript, start):
        last_idx = idx
        if msg is None:
            continue
        records.append({
            "session_id": session_id,
            "speaker": msg["speaker"],
            "text": msg["text"],
            "timestamp": msg["timestamp"],
            "uuid": msg["uuid"],
            "group_id": GROUP_ID,
        })

    if records:
        enqueue(records)
    state[session_id] = last_idx + 1
    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
