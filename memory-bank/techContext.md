# Tech context

## Stack

| Layer | Technology |
|--------|------------|
| Language (core) | Python 3 |
| API | FastAPI, Uvicorn |
| Agents | PydanticAI |
| UI | React 18, TypeScript, Vite 5, Tailwind 3 |
| UI charts (where used) | lightweight-charts |
| Chat markdown | react-markdown, remark-gfm, @tailwindcss/typography |

## Repo layout (short)

- `src/` — PEAD pipeline, data, news, agent, persistence, config (`src/config/settings.py`).
- `server/` — HTTP API, SSE chat.
- `web/` — Vite app, `npm run dev` (default port 5173).
- `scripts/dev.sh` / `make dev` — API + web together (see README).

## Environment

- **`OPENAI_API_KEY`** — Required for **chat** / PydanticAI paths. Core `/api/tools/*` PEAD runs do not require it unless a route invokes LLM (news headline synthesis + optional **`ai_digest`** when those toggles are on).
- Optional: `PEAD_CORS_ORIGINS`, `CHAT_SQLITE_PATH` (chat DB), etc. (see settings).

## Dev commands (typical)

```bash
./scripts/dev.sh    # or: make dev
# API often :8000, Vite :5173 — see README
```

## Constraints

- **Indian equities:** NSE symbols; index proxy `^NSEI` in config.
- **README memory block:** `PROJECT_MEMORY.md` section `## Current snapshot` syncs into `README.md` via `python3 scripts/sync_memory_readme.py` (intro line in the script points readers at `memory-bank/` first, then `PROJECT_MEMORY.md` for changelog).
