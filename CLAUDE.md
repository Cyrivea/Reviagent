# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reviagent — a single-user personal AI assistant. FastAPI backend + a single self-contained `index.html` frontend (SSE streaming, no build step). Runs on Zhipu GLM-4-flash via the `zhipuai` SDK. Deployed behind Nginx + Systemd on Aliyun (47.79.85.117).

## Commands

```bash
# Local syntax check before every commit (the project's lint gate)
python3 -m py_compile api.py rag.py && echo "OK"

# Run locally (dev)
uvicorn api:app --reload --port 8000

# Run as production does (start.sh)
uvicorn api:app --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop
```

There is no test suite. `python3 -m py_compile` is the only pre-push check.

### Deploy workflow (see `修改后更新服务器操作.md`)

Local: `py_compile` → `git add . && git commit && git push`.
Server: `git pull && sudo systemctl restart reviagent`, then `sudo systemctl status reviagent` to confirm.
The Systemd unit is named `reviagent`.

## Architecture

- **`api.py`** — all HTTP endpoints and the agent loop.
  - `/chat` (POST): the core flow. Runs RAG `search()` for context, builds a system prompt (persona + tool rules + optional profile + optional RAG context), then does a **single** GLM call to detect a tool call. If a tool is requested it executes one tool, appends the result, and re-calls GLM with `stream=True`; otherwise it streams `msg.content` directly. Responds as SSE (`text/event-stream`) with event types `tool`, `content`, `done`. The `done` event returns a cleaned `history` array the frontend resends on the next turn (assistant tool-call messages are stripped from history).
  - `/upload` (POST): saves the file to a tempfile, calls `rag.add_document`, unlinks the temp.
  - `/profile` (GET/POST): persisted to `user_profile.json`, injected into the system prompt — this is the multi-user-isolation gap (one global profile file today).
  - `/`, `/logo.png`, `/CascadiaMono.ttf`: serve the frontend assets via `FileResponse`.
- **`rag.py`** — RAG layer over ChromaDB (`PersistentClient(path="./chroma_db")`, collection `documents`). Embeddings via Zhipu `embedding-3`. `add_document` reads pdf/docx/txt/md, chunks at 500 chars, batch-embeds (one API call for all chunks to avoid rate limits), and stores with `source` filename metadata. `search` is guarded to return `[]` when the collection is empty.
- **`index.html`** — single-file frontend, no framework/bundler. Loads `marked` from CDN, parses the SSE stream, renders Markdown. Edit it directly.

### Tools (manual agent framework)

Tools are LangChain `@tool` functions (`calculate`, `search_web`, `get_current_time`) but GLM is driven by the hand-written `tools_schema` list and dispatched through `tools_map`. **Adding a tool requires editing three places in `api.py`**: the `@tool` function, an entry in `tools_schema`, and an entry in `tools_map`. The loop only ever executes the first tool call (`msg.tool_calls[0]`) and does not loop for multi-step tool use.

`search_web` uses `ddgs` (DuckDuckGo); it keyword-classifies queries as news vs. text and has a timeout fallback chain (news → text → failure message).

## Conventions & gotchas

- API key is read from `.env` as `API_KEY` (`load_dotenv()` → `ZhipuAI(api_key=...)`). `.env`, `user_profile.json`, `chroma_db/`, and the ops `.md` are git-ignored.
- Known roadmap (developer's stated TODO): SQLite persistence, Nginx-block the `.env`, real per-user profile isolation.
