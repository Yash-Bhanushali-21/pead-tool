# Active context

**Last reviewed:** 2026-05-01 (Memory Bank sync: Issue #2 — news intelligence enhancements)

## Current focus

- **Memory Bank** is the structured brain: `memory-bank/*.md` + `.cursor/rules/memory-bank.mdc` (always apply).
- **Platform reframe:** This is no longer a PEAD-only tool. It is a **production-grade stock research and intelligence platform** for Indian equities (NSE/BSE). News/event intelligence is a first-class primary signal layer alongside technicals and fundamentals.
- **Issue #2 — News Intelligence (completed on branch `issue-2-fix`):** Full upgrade to hedge-fund-grade news pipeline. See `progress.md` for the complete change list.
- **Data layer:** Pluggable **`OHLCVSource`** (`src/data/ohlcv_source.py`); **`DataManager`** merges NSE → Yahoo → jugaad with explicit cache and fallback logging.
- **Equity research pipeline:** `execute_pipeline` logs `equity_research.pipeline` stage start/done/fail with `run_id`, `symbol`, `duration_ms`. Now includes `run_exchange_announcements` stage.
- **Chat UI:** Session history sidebar, stick-to-bottom scroll, plain text while streaming → Markdown after.
- **README / changelog:** `PROJECT_MEMORY.md` **Current snapshot** + **Change log**; sync to README via `scripts/sync_memory_readme.py`.

## News pipeline (current state — post Issue #2)

Full pipeline: `NewsCollector.collect()` → title-fingerprint dedup → sentiment pipeline → signals → ai_digest → API response.

New modules in `src/news/`:
- `source_registry.py` — credibility weights (Tier 1–4) for all India sources; used in weighted scoring
- `dedup.py` — title-fingerprint dedup (collapses syndication copies)
- `event_classifier.py` — rule-based event taxonomy (EARNINGS, GUIDANCE, ANALYST_RATING, CORPORATE_ACTION, M_AND_A, REGULATORY, MANAGEMENT, MACRO_INDIA, SECTOR_CONTEXT, GENERAL)
- `news_signals.py` — `news_velocity`, `source_agreement`, `event_tone` quantitative signals
- `exchange_announcements.py` — NSE/BSE corporate filings fetcher (board meetings, results, corporate actions)

New pipeline stage: `run_exchange_announcements` (between `run_fundamentals_tool` and `run_technical_tool` in `EQUITY_RESEARCH_FULL_STAGES`).

New standalone API route: `POST /api/tools/run/exchange-announcements`.

New built-in India RSS feeds (Tier 2, always active, no config needed):
NDTV Profit, Mint/LiveMint, Business Standard, BusinessLine, Economic Times Markets, MoneyControl Results, Financial Express.

## Session continuity (for agents)

- **Start of substantive work:** Read **all** files under `memory-bank/` before planning or coding.
- User preference: treat Memory Bank as **first** stop so active context is not lost across days.

## Recent decisions (stable)

- Chat persistence: `CHAT_SQLITE_PATH`; `/api/chat/sessions` for list + history.
- Time: `src/utils/time_compat.py` (naive UTC) to avoid pandas tz crashes.
- **Market index for RS / benchmark:** `aligned_market_index_close` uses `DataManager.get_market_data` for `MARKET_INDEX` (default `^NSEI`).
- Trade readiness: `src/trade_context/` blended into synthesis when present.
- **News `ai_digest`:** Gated by `include_symbol_news_ai_digest` / `include_market_news_ai_digest`; `include_ai_digest` on `NewsToolRequest`.
- **Article preview / citations list:** `build_article_preview_rows` orders dated articles newest-first, then undated.
- **Source credibility weighting:** All sentiment aggregates now use weighted mean (source weight × event weight) instead of simple mean. EARNINGS/GUIDANCE articles get 2× weight.
- **`coverage_meta`:** Every news API response now includes tier counts, event type distribution, dedup stats, and quality label (high/medium/low_medium/low).
- **`news_signals`:** Every pipeline run (when window_start/end provided) computes `news_velocity`, `source_agreement`, `event_tone` in `news_sentiment.news_signals`.

## Next steps (deferred — pick up later)

- **Verify NSE announcements end-to-end:** Run `POST /api/tools/run/exchange-announcements` for a symbol with known recent board meetings; confirm items, dates, filing_types are correct. NSE API requires browser-like headers + cookie warm-up — may need tuning.
- **FinBERT optional path:** `NEWS_SENTIMENT_BACKEND=finbert` — not shipped yet (heavy torch dep). Design as a pluggable `SentimentBackend` class behind config flag.
- **Standalone News tool UI:** `POST /api/tools/run/news` supports `include_ai_digest`; no dedicated React page yet.
- **Zerodha OHLCV source:** Design auth + compliance (issues-to-fix README §4).
- **Data backlog:** Verify OHLCV calendar range edge cases (issues-to-fix §1).
- After milestones: bump `progress.md`, append `PROJECT_MEMORY.md` change log, run `sync_memory_readme.py`.

## Open questions

- Whether to also gate `_llm_synthesis` (headline JSON pass) independently from `ai_digest` — currently only the final digest is toggled.
- BSE announcements API auth — current fetcher hits NSE only; BSE has a different endpoint structure.
