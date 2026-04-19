# Issues to fix (backlog)

Research / product backlog for the PEAD tool. Items are **not** commitments or timelines; they track known gaps and desired enhancements.

---

## 1. OHLCV fetch for explicit calendar ranges

**Problem:** Historical daily OHLCV for a user-selected window (e.g. multi-year range) does not always match the requested span on the chart. Vendors can return a **tail-only** slice, truncated starts, or divergent coverage vs the UI “requested window”.

**Direction:**

- Continue hardening **multi-vendor merge** (NSE, Yahoo with `period=max` repair where needed, jugaad-data) and **cache invalidation** when merge semantics change.
- Evaluate **additional or alternate sources** where listing date / feed limits still leave gaps after all current paths.
- Keep **requested vs actual bar window** visible in the UI for transparency.

**Status:** In progress (pipeline + `DataManager`); further source work TBD.

---

## 2. News sentiment and market sentiment — broader article coverage

**Problem:** Symbol news and market-context flows rely heavily on **Google News** and **Bing**-style discovery. That limits article count and diversity, which weakens aggregate sentiment and context.

**Direction:**

- Add **more RSS / HTML / feed sources** (India tape, exchanges, credible wires) consistent with “research-only” and rate limits.
- Deduplicate by URL/title and preserve citation metadata for the UI.
- Document source list, limits, and compliance (robots, terms) in repo docs.

**Status:** Partially addressed — extra Google query variants, configurable RSS feeds (`PEAD_NEWS_EXTRA_RSS_FEEDS`), Bing multi-query, and market RSS keyword pass; extend with more licensed feeds as needed.

---

## 3. Final AI layer on news outputs — rationale and key points

**Problem:** After articles are fetched and scored, there is no **single consolidated LLM pass** that explains *why* the net sentiment skew looks the way it does, with **actionable lines** tied to headlines (e.g. geopolitical / sector / company-specific drivers).

**Direction:**

- Add a **final summarisation step** (post collection + existing sentiment aggregation) that outputs roughly **5–6 lines** of rationale plus **bullet key points** (entities, events, risks).
- Require **`OPENAI_API_KEY`** (or configured model) on the server; fail closed or degrade gracefully when absent.
- Keep outputs **research-only** (no buy/sell); align with institutional-style disclaimer in product copy.

**Status:** Implemented — `ai_digest` on symbol + market sentiment payloads (`rationale`, `key_points`, `tone_alignment`, `limitations`); toggle via `NEWS_AI_DIGEST_ENABLED`, model via `OPENAI_NEWS_DIGEST_MODEL` (falls back to `OPENAI_NEWS_MODEL`).

---

## How to use this file

- Treat each item as a **ticket-sized epic**; break into PRs when picking up work.
- After shipping a item, move detail to `PROJECT_MEMORY.md` / `memory-bank/progress.md` and tick or remove the section here.
