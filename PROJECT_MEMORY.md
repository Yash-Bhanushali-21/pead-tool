# Project memory (canonical context)

**Purpose:** **Change log** and **README snapshot** source; high-level snapshot lines below feed `README.md` via `scripts/sync_memory_readme.py`.

**Structured durable context** (scope, architecture, stack, active focus) lives in **`memory-bank/*.md`**. Cursor agents must **read all Memory Bank files at task start** per `.cursor/rules/memory-bank.mdc`, then use this file for dated changes and README sync.

**Not investment advice.** This file describes software and research workflows only.

---

## Current snapshot

- **Memory Bank:** Durable context in `memory-bank/` (read all `.md` there at task start); Cursor rule `.cursor/rules/memory-bank.mdc` (always apply). This file remains the **change log** + **README snapshot** source.
- **News layer:** Optional article **scraping** (trafilatura) + metadata; aggregate **bullish/bearish/neutral** media stance; optional final OpenAI **`ai_digest`** (toggle per run on equity single + `/api/tools/run/news` + agent tool). **`articles_preview`** uses dated-then-undated ordering so HTML discovery / undated rows are not dropped under tight preview caps; citations rows carry **`collector_source`** / **`body_scrape_present`** in metadata.
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
| 2026-04-19 | News / docs | **`ai_digest` toggles** (symbol + market) on equity research + `PeadSingleRequest`; `include_ai_digest` on `NewsToolRequest`; agent `run_news_and_sentiment`; UI checkboxes on single-symbol tool + `ai_digest_skipped_by_request` messaging. **`articles_preview`** via `build_article_preview_rows` (dated then undated, URL dedupe). **`per_article`** lexicon cap raised. Citations **`metadata_json`**: `collector_source`, `body_scrape_present`. Memory Bank + this snapshot updated; **E2E citations UI** verification deferred. |
| 2026-04-12 | News / UX | User report: news + **citations tool not working as expected** — logged in `memory-bank/progress.md` for follow-up (repro, SQLite, UTC filter, API). |
| 2026-04-12 | News | Article **web scraping** (trafilatura) for first N URLs; **metadata** (hostname, author, date, word count); **bullish/bearish/neutral** aggregate (`stock_media_stance`, `per_article`); Google RSS query fixed (removed stray symbol); News tool API/UI: `end_date`, `scrape_bodies`, `max_scrape`. |
| 2026-04-11 | Cursor / docs | Introduced **Memory Bank** (`memory-bank/*.md`), always-apply rule `.cursor/rules/memory-bank.mdc`; retired `00-project-memory.mdc` (merged into Memory Bank rule). |
| 2026-04-11 | Trade context | Added `trade_context` (liquidity, vol regime, alignment, model fit) + blend pillar; agent tools `get_execution_context_snapshot`, `get_yahoo_calendar_snippet`; synthesis brief section — research-only disclaimers. |
| 2026-04-11 | Data / NSE | NSE fetchers now pass `datetime.date` (not DD-MM-YY strings); `fetch_historical_index_data` uses positional `index` + `to_calendar_date` (`src/data/nse_fetcher.py`, `time_compat`, Yahoo fallback). |
| 2026-04-11 | PEAD / API | Fixed tz-naive vs tz-aware crash on `/api/tools/run/single`: `src/utils/time_compat.py`, normalize announcement anchor in `analyze_announcement`. |
| 2026-04-11 | Cursor / docs | Added `scripts/sync_memory_readme.py`, refined README snapshot + rules (memory workflow, FE/BE, institutional tone disclaimer). |
| 2026-04-11 | Cursor / docs | Added `PROJECT_MEMORY.md`, README memory snapshot, `.cursor/rules` (memory, FE, BE, analyst tone). |

---

## Open questions / backlog

- **News + citations:** Re-verify with a repro run (RSS + HTML discovery mix): `articles_preview`, `per_article`, `persisted_citations`, citations list API + UTC `fetched_date` vs UI. Prior “not working” report partially addressed by preview ordering + metadata; remaining issues tracked in **`memory-bank/progress.md`**.
- **Optional:** Standalone news tool page UI for `include_ai_digest` (API already supports). Optional separate toggle for headline **`_llm_synthesis`** vs **`ai_digest`**.

---

## How to update

After **substantive** code or behavior changes:

1. Append a row to **Change log** above.
2. Refresh **Current snapshot** if architecture or workflows shifted.
3. Run `python3 scripts/sync_memory_readme.py` to refresh the README snapshot block (or edit the README markers by hand).

Optional: add a **git pre-commit** hook that runs `scripts/sync_memory_readme.py` when `PROJECT_MEMORY.md` changes—Cursor does not do this automatically.
