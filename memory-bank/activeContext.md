# Active context

**Last reviewed:** 2026-04-19 (news layer + Memory Bank — user: document achievements / remaining work)

## Current focus

- **Memory Bank** is the structured brain: `memory-bank/*.md` + `.cursor/rules/memory-bank.mdc` (always apply).
- **News research:** Headline collection (RSS, Bing, DDG-lite, HTML discovery, etc.), optional **full-article scrape** (`trafilatura`), TextBlob + optional OpenAI headline synthesis, optional final **`ai_digest`** narrative; citations persisted to SQLite (`news_article_citations`). **Equity single tool** exposes testing toggles for `ai_digest` per pass.
- **Chat UI:** Session history sidebar, stick-to-bottom scroll, plain text while streaming → Markdown after. App layout uses flex + `min-h-0`.
- **README / changelog:** `PROJECT_MEMORY.md` **Current snapshot** + **Change log**; sync to README via `scripts/sync_memory_readme.py`.

## Session continuity (for agents)

- **Start of substantive work:** Read **all** files under `memory-bank/` (not only this file) before planning or coding.
- **Always-apply rule** reminds every chat, but **file contents are not auto-loaded** into context until read or `@`-mentioned — so when in doubt, **read** `memory-bank/` or ask the user to attach `@memory-bank/activeContext.md` (and siblings if needed).
- User preference (confirmed): treat Memory Bank as **first** stop so active context is not lost across days.

## Recent decisions (stable)

- Chat persistence: `CHAT_SQLITE_PATH`; `/api/chat/sessions` for list + history.
- Time: `src/utils/time_compat.py` (naive UTC) to avoid pandas tz crashes.
- Trade readiness: `src/trade_context/` blended into synthesis when present; research-only disclaimers.
- **News `ai_digest`:** Gated by `include_symbol_news_ai_digest` / `include_market_news_ai_digest` on equity research options and `PeadSingleRequest`; `include_ai_digest` on `NewsToolRequest` (`POST /api/tools/run/news`); agent tool `run_news_and_sentiment` accepts `include_ai_digest`. When skipped, payload includes `ai_digest_skipped_by_request` for UI copy.
- **Article preview / citations list:** `build_article_preview_rows` (`src/news/article_preview.py`) orders **dated articles (newest first) then undated** (dedupe by URL) so HTML discovery and other undated hits are not dropped when preview cap is tight after lexicographic sort by `published`.

## Next steps (deferred — pick up later)

- **Verify end-to-end:** Long window + symbol known to yield `html_discovery` rows; confirm they appear in `articles_preview`, `per_article`, and SQLite citations UI/API (`GET /api/news/articles` if used).
- **News + citations “still broken” reports:** If any remain, reproduce with checklist in `progress.md` (SQLite path, `fetched_date` UTC vs UI filter, `persisted_citations`, scrape failures).
- **Standalone News tool UI:** Backend supports `include_ai_digest` on `/api/tools/run/news`; there is **no** dedicated `NewsToolPage.tsx` in repo today — add checkboxes there if a standalone page is introduced or linked from `/tools`.
- After milestones: bump `progress.md`, append `PROJECT_MEMORY.md` change log, run `sync_memory_readme.py` if snapshot changes.
- Optional: code-split heavy chat client deps if bundle size hurts.

## Open questions

- Whether to also gate **`_llm_synthesis`** (headline JSON pass) independently from **`ai_digest`** — currently only the final digest is toggled; headline LLM remains when API key is set.
