# Progress

## What works

- PEAD pipeline, scoring, CLI and tooling (see README).
- FastAPI: tool routes, streaming chat with SQLite session persistence.
- Web: Chat (`/`) with SSE streaming, Markdown after stream, session sidebar, mobile drawer + desktop collapse, scroll tuned for streaming + “Jump to latest”.
- Tools hub and tool pages under `/tools`.
- **Docs / process:** `memory-bank/` (six core files), `PROJECT_MEMORY.md` (changelog + README snapshot source), `scripts/sync_memory_readme.py`, `.cursor/rules/memory-bank.mdc`.
- **Data & observability (2026-04-19):**
  - **`OHLCVSource`** protocol (`src/data/ohlcv_source.py`); **`DataManager`** registers NSE / Yahoo / Jugaad; **`from src.data import DataManager, OHLCVSource`** via `src/data/__init__.py`.
  - **Vendor logging:** Structured **`data_fetch`** lines (source, kind, symbol/API, calendar window, row counts / bar range); **`data_manager.get_stock_data` / `get_market_data`** log cache hit/miss and Yahoo/Jugaad fallback reasons.
  - **Market index bugfix:** Relative-strength benchmark uses **`get_market_data`** / Yahoo **`get_index_data`** for **`^NSEI`** — avoids invalid **`^NSEI.NS`** from treating the index like an NSE equity ticker (`src/technical/market_benchmark.py`, `src/data/yahoo_fetcher.py`).
- **Equity research pipeline logging:** `execute_pipeline` (`src/equity_research_pipeline/runner.py`) — per-stage timing and failures; **`equity_research_log_adapter`** + **`format_equity_run_ctx`**; **`full_run_steps`** / **`scoring_steps`** / **`stock_analyzer`** / **`desk_insight`** — stage and LLM logs with **`exc_info`** on errors where appropriate.
- **News / sentiment (2026-04-19 milestone):**
  - **Final OpenAI `ai_digest`** can be turned off for testing: `EquityResearchRunOptions.include_symbol_news_ai_digest` / `include_market_news_ai_digest`, threaded through `StockAnalyzer.analyze_equity_research`, `full_run_steps`, `PeadSingleRequest` + `POST /api/tools/run/single`, and **`NewsToolRequest`** for `POST /api/tools/run/news`. Agent tool `run_news_and_sentiment` accepts `include_ai_digest`.
  - **Web:** `PeadSingleToolPage.tsx` — two checkboxes for symbol vs market `ai_digest`; `PeadSingleResultView.tsx` distinguishes **request-skipped** vs **key/config/error** skips via `ai_digest_skipped_by_request`.
  - **`articles_preview`:** Built with `build_article_preview_rows` in `src/news/article_preview.py` (dated newest-first, then undated, URL dedupe) so **HTML discovery** and other undated articles are not silently truncated off the preview list.
  - **`per_article` default cap** increased (lexicon rows for more articles) in `src/news/sentiment_pipeline.py`.
  - **Citations DB:** `persist_fetch` enriches `metadata_json` with `collector_source` and `body_scrape_present` (`src/persistence/sqlite_news_articles.py`).

## Known gaps / backlog

- **Optional OHLCV vendor:** **Zerodha (Kite Connect)** as a candle/OHLCV source for wider or finer-grained technical coverage — tracked in **`issues-to-fix/README.md`** §4 (auth, merge policy, compliance TBD).
- **News + citations — follow-up verification:** Re-run a symbol/window rich in RSS + HTML discovery; confirm `articles_preview`, `per_article`, `persisted_citations`, and any **citations browser** (`GET /api/news/articles`, UTC `fetched_date` filter vs UI) behave as expected. Touch points if issues persist: `src/news/layer.py`, `src/news/collector.py`, `src/persistence/sqlite_news_articles.py`, `server/news_routes.py` (if present), web citations consumer.
- **Standalone News UI:** API supports `include_ai_digest`; no dedicated news-only React page in repo — add UI when/if `/tools/news` (or similar) ships.
- **Optional product knob:** Independent toggle for headline **`_llm_synthesis`** vs **`ai_digest`** (only digest is gated today).
- Open items: see `activeContext.md` and `PROJECT_MEMORY.md` → Open questions.
- Large JS bundle on chat route (markdown stack); optional code-splitting later.

## Milestone mirror (high level)

Canonical table: **`PROJECT_MEMORY.md` → Change log** (append-only, newest first).

| Date (UTC) | Note |
|------------|------|
| 2026-04-19 | Data: `OHLCVSource` + `DataManager` exports; `data_fetch` / `data_manager` logging; market index fetch fix (`^NSEI`). Equity pipeline + scoring + desk logging. Backlog: Zerodha fetcher (`issues-to-fix/README.md`). Memory Bank + `PROJECT_MEMORY` + README sync. |
| 2026-04-19 | News: `ai_digest` toggles (equity single + API + agent); preview ordering for undated/HTML discovery; citation metadata flags; Memory Bank + `PROJECT_MEMORY` updated. |
| 2026-04-12 | Full Memory Bank review; `activeContext` + `progress` refreshed; documented **session continuity** (read `memory-bank/*.md` at task start; `@` mention when user wants guaranteed load). |
| 2026-04-11 | Memory Bank workflow introduced; `memory-bank.mdc`; merged old `00-project-memory.mdc`. |

For full history see **`PROJECT_MEMORY.md`**.
