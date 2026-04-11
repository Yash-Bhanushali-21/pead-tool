# Project memory (canonical context)

**Purpose:** Single source of truth for **progress, decisions, and recent changes**. Cursor agents must **read this file first** before substantial work, and **update it** after material changes (see `.cursor/rules`).

**Not investment advice.** This file describes software and research workflows only.

---

## Current snapshot

- **Stack:** Python PEAD pipeline (NSE/Yahoo), FastAPI (`server/`), PydanticAI agents (`src/agent/`), React + Vite + Tailwind (`web/`).
- **Entry:** CLI `main.py`; dev boot `./scripts/dev.sh` or `npm run dev` (repo root); UI at `/` (chat) and `/tools` (direct PEAD runs).
- **Config:** `src/config/settings.py`; `OPENAI_API_KEY` required for **chat agent**; `/api/tools/*` core PEAD does not require it.
- **Memory sync:** After editing this section, run `python3 scripts/sync_memory_readme.py` or manually update the README block between `MEMORY_SNAPSHOT` markers.
- **Time:** Event anchors use `src/utils/time_compat.py` (naive UTC) so API/feed timestamps never trip pandas tz-naive vs tz-aware comparisons.
- **Trade readiness:** `src/trade_context/` adds execution-context scoring (not a trade recommendation); folded into synthesis blend when present.

---

## Conventions (do not break without updating this file)

- Run output lives under `output/` with timestamped subfolders; agent runs use `output/agent_runs/` by default.
- Indian equities: symbols as NSE; market proxy `^NSEI` in config.
- News: Yahoo + Google News RSS; optional OpenAI for news synthesis layer.

---

## Change log (newest first)

| Date (UTC) | Area | Summary |
|------------|------|---------|
| 2026-04-11 | Trade context | Added `trade_context` (liquidity, vol regime, alignment, model fit) + blend pillar; agent tools `get_execution_context_snapshot`, `get_yahoo_calendar_snippet`; synthesis brief section — research-only disclaimers. |
| 2026-04-11 | Data / NSE | NSE fetchers now pass `datetime.date` (not DD-MM-YY strings); `fetch_historical_index_data` uses positional `index` + `to_calendar_date` (`src/data/nse_fetcher.py`, `time_compat`, Yahoo fallback). |
| 2026-04-11 | PEAD / API | Fixed tz-naive vs tz-aware crash on `/api/tools/run/single`: `src/utils/time_compat.py`, normalize announcement anchor in `analyze_announcement`. |
| 2026-04-11 | Cursor / docs | Added `scripts/sync_memory_readme.py`, refined README snapshot + rules (memory workflow, FE/BE, institutional tone disclaimer). |
| 2026-04-11 | Cursor / docs | Added `PROJECT_MEMORY.md`, README memory snapshot, `.cursor/rules` (memory, FE, BE, analyst tone). |

---

## Open questions / backlog

- (Add items as they arise.)

---

## How to update

After **substantive** code or behavior changes:

1. Append a row to **Change log** above.
2. Refresh **Current snapshot** if architecture or workflows shifted.
3. Run `python3 scripts/sync_memory_readme.py` to refresh the README snapshot block (or edit the README markers by hand).

Optional: add a **git pre-commit** hook that runs `scripts/sync_memory_readme.py` when `PROJECT_MEMORY.md` changes—Cursor does not do this automatically.
