# graphiti-memory

Cross-session, long-term memory for [Claude Code](https://claude.com/claude-code), running **100% locally**. Every Claude conversation on your machine is captured, distilled into a temporal knowledge graph with [Graphiti](https://github.com/getzep/graphiti), and made available to future sessions — so Claude remembers what you told it yesterday, in a different session, in a different repo.

No cloud, no API keys: a local [Ollama](https://ollama.com) model does the entity extraction, [Neo4j](https://neo4j.com) stores the graph.

---

## What it does

- **Captures** every session's messages automatically (a Claude Code `Stop` hook).
- **Ingests** them in the background into a temporal knowledge graph (entities, relationships, and *when* each fact was true — superseded facts are marked expired).
- **Recalls** on every new session start: a digest of what's known about you is injected as context (a `SessionStart` hook).
- **On-demand** tools via MCP: `remember(fact)` and `search_memory(query)`.

## Architecture

```
Every Claude Code session
   ├─ SessionStart hook ─→ Cypher digest of recent facts ─→ injected as context
   └─ Stop hook ─────────┐
   MCP remember() ───────┼─→ queue.jsonl ──→ worker (launchd) ──→ Graphiti ──→ Neo4j
   MCP search_memory() ──── live hybrid search over the graph
```

Two producers (the Stop hook and the MCP server) only ever **append** to one queue file and return immediately. A single independent worker daemon drains the queue into Graphiti. Nothing ingests inline, because local extraction is slow — so a fact becomes searchable within seconds-to-minutes, not instantly (**eventual consistency**).

## Requirements

- macOS (the autostart uses `launchd`; the rest is portable)
- Docker (for Neo4j)
- Python 3.12+
- Ollama

## Setup

### 1. Neo4j (Docker)

```bash
docker run -d --name graphiti-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/CHANGE_ME \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v graphiti-neo4j-data:/data \
  --restart unless-stopped \
  neo4j:5.26
```

Browser UI at http://localhost:7474 (user `neo4j`).

### 2. Ollama models

An instruct model for extraction + an embedder. 14B gives noticeably more accurate extraction than 7B (fewer hallucinated facts), at the cost of speed:

```bash
ollama pull qwen2.5:14b-instruct        # or hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
ollama pull nomic-embed-text            # or hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q4_K_M
```

> If your network blocks Ollama's own registry, pull from Hugging Face instead using the `hf.co/...` names above.

### 3. Python environment

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### 4. Configuration

```bash
cp .env.sample .env
# edit .env — set NEO4J_PASSWORD, and the model names if you changed them
```

| Variable | Meaning |
|---|---|
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j connection |
| `OLLAMA_BASE_URL` | Ollama OpenAI-compatible endpoint (`http://localhost:11434/v1`) |
| `LLM_MODEL` / `EMBED_MODEL` / `EMBED_DIM` | extraction model, embedder, embedding dim |
| `USER_NAME` | how you're labelled in the graph |
| `GROUP_ID` | namespace; keep one value to share memory across all sessions |
| `SEMAPHORE_LIMIT` | keep at `1` for local models (they choke on concurrent structured output) |
| `INGEST_ASSISTANT` | `0` = store only your messages (recommended); `1` = also store Claude's replies |

Verify the stack:

```bash
./.venv/bin/python smoke_test.py
```

## Claude Code integration

### Hooks (`~/.claude/settings.json`)

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "/ABS/PATH/.venv/bin/python /ABS/PATH/memory/session_context.py 2>/dev/null || true",
        "timeout": 15 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "/ABS/PATH/.venv/bin/python /ABS/PATH/memory/capture_hook.py 2>/dev/null || true",
        "timeout": 30 } ] }
    ]
  }
}
```

### MCP server

```bash
claude mcp add graphiti-memory --scope user -- \
  /ABS/PATH/.venv/bin/python /ABS/PATH/memory/mcp_server.py
```

### Worker daemon (launchd)

The worker must run continuously. Create `~/Library/LaunchAgents/com.example.graphiti-worker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.graphiti-worker</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ABS/PATH/.venv/bin/python</string>
    <string>/ABS/PATH/memory/worker.py</string>
  </array>
  <key>WorkingDirectory</key><string>/ABS/PATH/memory</string>
  <key>EnvironmentVariables</key><dict><key>SEMAPHORE_LIMIT</key><string>1</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.example.graphiti-worker.plist
```

> `.plist` files are gitignored because they hardcode absolute paths. Copy the template above and set `/ABS/PATH` to your checkout.

## Usage

```bash
# Ask your memory anything
./.venv/bin/python ask.py "what am I working on?"

# Bulk-ingest a chat export ( [{ "speaker": "...", "text": "...", "timestamp": "ISO8601" }] )
./.venv/bin/python ingest_chat.py my_chat.json my-group
```

Inside Claude, the MCP tools are available automatically:
- `remember("...")` — store a durable fact.
- `search_memory("...")` — live search.

## Files

```
config.py            Graphiti wiring (Ollama + Neo4j), reads .env
ask.py               CLI search
ingest_chat.py       bulk-ingest a chat JSON export
smoke_test.py        end-to-end sanity check
memory/
  common.py          transcript parsing + queue helpers
  capture_hook.py    Stop hook: enqueue new messages
  worker.py          launchd daemon: drain queue -> Graphiti
  session_context.py SessionStart hook: Cypher digest -> context
  mcp_server.py      MCP tools: remember / search_memory
```

## Notes

- **Latency.** Extraction runs one message at a time on a local model, so heavy multi-session use builds a backlog that drains when idle. Check progress: `wc -l memory/queue.jsonl` vs `cat memory/worker.offset`.
- **Extraction quality.** Smaller models occasionally invent or misattribute facts. Prefer 14B+ for a memory you want to trust. Assistant replies are not ingested by default (they tend to get misattributed).
- **Privacy.** `queue.jsonl`, `state.json`, and the logs contain your real conversation text and are gitignored. So is `.env`. Never commit them.

## License

MIT
