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
- **`src/data/`** — **`DataManager`** façade over **`OHLCVSource`** implementations (**NSE**, **Yahoo**, **Jugaad**); merge/fallback and pickle cache; grep-friendly logs (`data_fetch`, `data_manager.*`). Re-export: `from src.data import DataManager, OHLCVSource`.
- `server/` — HTTP API, SSE chat.
- `web/` — Vite app, `npm run dev` (default port 5173).
- `scripts/dev.sh` / `make dev` — API + web together (see README). Ports default **8000** / **5173** (`UVICORN_PORT` / `VITE_PORT` for `scripts/dev.sh`).

## Environment

- **`OPENAI_API_KEY`** — Required for **chat** / PydanticAI paths. Core `/api/tools/*` PEAD runs do not require it unless a route invokes LLM (news headline synthesis + optional **`ai_digest`** when those toggles are on).
- Optional: `PEAD_CORS_ORIGINS`, `CHAT_SQLITE_PATH` (chat DB), etc. (see settings).

## Dev commands (typical)

```bash
./scripts/dev.sh    # or: make dev
# API often :8000, Vite :5173 — see README
```

## Constraints

- **Indian equities:** NSE symbols; index proxy **`MARKET_INDEX`** (default **`^NSEI`**) in config. Benchmark/RS code uses **`DataManager.get_market_data`** (NSE NIFTY + Yahoo index) — not the equity stock path for the index ticker.
- **README memory block:** `PROJECT_MEMORY.md` section `## Current snapshot` syncs into `README.md` via `python3 scripts/sync_memory_readme.py` (intro line in the script points readers at `memory-bank/` first, then `PROJECT_MEMORY.md` for changelog).
