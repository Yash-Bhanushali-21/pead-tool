# Progress

## What works

- PEAD pipeline, scoring, CLI and tooling (see README).
- FastAPI: tool routes, streaming chat with SQLite session persistence.
- Web: Chat (`/`) with SSE streaming, Markdown after stream, session sidebar, mobile drawer + desktop collapse, scroll tuned for streaming + "Jump to latest".
- Tools hub and tool pages under `/tools`.
- **Docs / process:** `memory-bank/` (six core files), `PROJECT_MEMORY.md` (changelog + README snapshot source), `scripts/sync_memory_readme.py`, `.cursor/rules/memory-bank.mdc`.
- **Data & observability (2026-04-19):**
  - **`OHLCVSource`** protocol (`src/data/ohlcv_source.py`); **`DataManager`** registers NSE / Yahoo / Jugaad; `from src.data import DataManager, OHLCVSource` via `src/data/__init__.py`.
  - **Vendor logging:** Structured `data_fetch` lines; `data_manager.get_stock_data` / `get_market_data` log cache hit/miss and fallback reasons.
  - **Market index bugfix:** RS benchmark uses `get_market_data` / Yahoo `get_index_data` for `^NSEI`.
- **Equity research pipeline logging (2026-04-19):** `execute_pipeline` per-stage timing; `equity_research_log_adapter`; `full_run_steps` / `scoring_steps` / `stock_analyzer` / `desk_insight` stage logs.
- **News / sentiment (2026-04-19):**
  - `ai_digest` toggles (equity single + API + agent); preview ordering for undated/HTML discovery; citation metadata flags.
  - `per_article` default cap increased; `build_article_preview_rows` with undated ordering.
  - Citations DB: `persist_fetch` enriches `metadata_json` with `collector_source` and `body_scrape_present`.

## Issue #2 — News Intelligence Enhancements (2026-05-01, branch `issue-2-fix`)

### New files

| File | Purpose |
|---|---|
| `src/news/source_registry.py` | Credibility-tiered source weights (Tier 1–4); 50+ Indian/global sources mapped; config-overridable via `NEWS_SOURCE_WEIGHTS` JSON env |
| `src/news/dedup.py` | Title-fingerprint dedup: normalise → SHA-1 → keep highest-credibility source copy; collapses syndication copies |
| `src/news/event_classifier.py` | Rule-based event taxonomy: EARNINGS, GUIDANCE, ANALYST_RATING, CORPORATE_ACTION, M_AND_A, REGULATORY, MANAGEMENT, MACRO_INDIA, SECTOR_CONTEXT, GENERAL; 150+ keyword rules, word-boundary aware |
| `src/news/news_signals.py` | Three quantitative signals: `news_velocity` (articles/day + label), `source_agreement` (weighted StdDev over Tier 2+ sources), `event_tone` (weighted sentiment restricted to EARNINGS+GUIDANCE articles) |
| `src/news/exchange_announcements.py` | NSE corporate filings fetcher (announcements + corporate actions endpoints); returns `NewsArticle` list pre-classified by filing type; `build_announcements_summary` for API response |
| `web/src/lib/equityPipelineStages.ts` | Previously missing — all stage IDs + labels including new `run_exchange_announcements` |
| `web/src/lib/toolsConfig.ts` | Previously missing — `ToolsConfig` interface with new news intelligence fields |
| `web/src/lib/formatYmd.ts` | Previously missing — `formatYmdOnly` utility |
| `web/src/lib/apiError.ts` | Previously missing — `formatApiError` for FastAPI error parsing |

### Modified files

| File | Change |
|---|---|
| `src/news/collector.py` | Added 7 built-in Tier-2 India RSS feeds (NDTV Profit, Mint, Business Standard, BusinessLine, ET Markets, MoneyControl Results, Financial Express); title-fingerprint dedup wired at end of `collect()`; `_india_financial_rss_symbol_scoped` + `_india_financial_rss_market` methods |
| `src/news/sentiment_pipeline.py` | Full rewrite: source credibility weighting + event-type weighting (EARNINGS/GUIDANCE 2×) in aggregate; `per_article` enriched with `event_type`, `source_weight`, `source_tier`; `coverage_meta` block; `news_signals` block; `window_start`/`window_end` args threaded through |
| `src/news/layer.py` | Passes `window_start`/`window_end` to `run_news_sentiment_pipeline` |
| `src/news/market_sentiment_layer.py` | Same; built-in India feeds called via `collect_from_extra_rss_market` |
| `src/config/config.py` | New keys: `NEWS_DEDUP_TITLE_ENABLED`, `NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED`, `NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S`, `NEWS_SOURCE_WEIGHTS` |
| `src/equity_research_pipeline/options.py` | New field: `include_exchange_announcements: bool = True` |
| `src/equity_research_pipeline/full_run_steps.py` | New stage `stage_run_exchange_announcements`; registered in `EQUITY_RESEARCH_FULL_STAGES` between `run_fundamentals_tool` and `run_technical_tool` |
| `src/analysis/stock_analyzer.py` | `analyze_equity_research` accepts + threads `include_exchange_announcements` |
| `server/tools_routes.py` | `PeadSingleRequest` + `tools_config` updated; new `ExchangeAnnouncementsRequest` model + `POST /api/tools/run/exchange-announcements` route |
| `web/src/components/tools/EquityPipelineStagePicker.tsx` | `PRESET_NEWS_INTEL` preset (exchange announcements + news + market sentiment); "News intelligence" preset button |
| `web/src/pages/tools/PeadSingleToolPage.tsx` | `includeExchangeAnnouncements` state + checkbox + request body wiring |

### New API surface

| Endpoint | What it does |
|---|---|
| `POST /api/tools/run/exchange-announcements` | Standalone NSE/BSE filings fetch for a symbol + date range; no full pipeline required |

### New response fields (in `news_sentiment` payload)

| Field | Description |
|---|---|
| `coverage_meta` | Tier counts, event type distribution, dedup removed count, quality label + reason |
| `news_signals` | `news_velocity` (articles/day, label), `source_agreement` (Tier 2+ StdDev → 0–1), `event_tone` (EARNINGS+GUIDANCE weighted score 0–100) |
| `per_article[].event_type` | EARNINGS / GUIDANCE / ANALYST_RATING / etc. |
| `per_article[].source_weight` | 0.0–1.0 credibility weight for this source |
| `per_article[].source_tier` | tier1 / tier2 / tier3 / tier4 |

### New pipeline stage

| Stage ID | Position | Opt-out |
|---|---|---|
| `run_exchange_announcements` | After `run_fundamentals_tool`, before `run_technical_tool` | Uncheck in stage picker or set `include_exchange_announcements=false` |

### Config keys added

| Key | Default | Purpose |
|---|---|---|
| `NEWS_DEDUP_TITLE_ENABLED` | `true` | Title-fingerprint dedup on/off |
| `NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED` | `true` | NSE/BSE announcements fetcher on/off |
| `NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S` | `15` | HTTP timeout for exchange APIs |
| `NEWS_SOURCE_WEIGHTS` | `""` | JSON dict to override any source credibility weight |

## Known gaps / backlog

- **NSE announcements verification:** Test with a symbol that had recent board meetings; confirm filing dates, types, attachment flags are correct. NSE API requires cookie warm-up (homepage hit) — may need retries for cold starts.
- **BSE announcements:** Current fetcher targets NSE only; BSE has a different endpoint. Wire BSE when auth/endpoint is confirmed stable.
- **FinBERT optional path:** Design as pluggable `SentimentBackend` (TextBlob / FinBERT / LLM); gated behind `NEWS_SENTIMENT_BACKEND=finbert`. Not shipped — avoids torch dependency for default installs.
- **Standalone News tool UI:** `POST /api/tools/run/news` is fully capable; no dedicated React page yet.
- **Zerodha OHLCV source:** Not started — design auth + compliance (issues-to-fix §4).
- **OHLCV calendar range edge cases:** issues-to-fix §1, in progress.
- Large JS bundle on chat route (markdown stack); optional code-splitting later.

## Milestone mirror (high level)

Canonical table: **`PROJECT_MEMORY.md` → Change log** (append-only, newest first).

| Date (UTC) | Note |
|------------|------|
| 2026-05-01 | Issue #2: News intelligence enhancements on branch `issue-2-fix`. New modules: source_registry, dedup, event_classifier, news_signals, exchange_announcements. Enhanced: collector (7 Tier-2 India RSS feeds, title dedup), sentiment_pipeline (weighted scoring, coverage_meta, news_signals), layer.py, market_sentiment_layer.py, full_run_steps (new stage run_exchange_announcements), tools_routes (new /run/exchange-announcements), options.py. Frontend: created all missing lib/ files; new stage in picker; new checkbox. |
| 2026-04-19 | Data: `OHLCVSource` + `DataManager` exports; `data_fetch` / `data_manager` logging; market index fetch fix (`^NSEI`). Equity pipeline + scoring + desk logging. Backlog: Zerodha fetcher. Memory Bank + `PROJECT_MEMORY` + README sync. |
| 2026-04-19 | News: `ai_digest` toggles (equity single + API + agent); preview ordering for undated/HTML discovery; citation metadata flags; Memory Bank + `PROJECT_MEMORY` updated. |
| 2026-04-12 | Full Memory Bank review; `activeContext` + `progress` refreshed; documented session continuity. |
| 2026-04-11 | Memory Bank workflow introduced; `memory-bank.mdc`; merged old `00-project-memory.mdc`. |

For full history see **`PROJECT_MEMORY.md`**.
