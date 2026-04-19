# News coverage: why counts stay low and how production systems scale

## What you see in the UI (fact)

For a **multi-year** window, a **small-cap** or **low-media** name often has **few distinct English headlines** in open RSS / web-discovery paths. The tool also **drops undated** hits when you apply a strict posted-date window (except DuckDuckGo lite, which often has no date).

That is a **data availability** limit, not only a bug.

## What “production” desks actually use (inference)

Institutional workflows rarely rely on a single Google RSS scrape. Typical layers:

| Tier | Examples | Role |
|------|----------|------|
| **Licensed aggregators** | Factiva, LexisNexis, Bloomberg, Refinitiv, RavenPack, AlphaSense | Broad history, dedupe, entity tagging, compliance |
| **Exchange / issuer primary** | NSE/BSE announcements, company IR RSS/email alerts | Filings, board outcomes, structured events |
| **Commercial news APIs** | NewsAPI.org, GDELT, Aylien, Event Registry | Programmatic `from`/`to` windows, pagination |
| **Vendor NLP** | Proprietary sentiment on top of the above | Stable training data, audit trail |

This repo stays **research-only** and **unlicensed-by-default**; we stack **free / low-cost** paths first.

## HTML search discovery (extra URLs)

For **more headline URLs** (not yet full bodies), the collector can parse **Bing web** and **DuckDuckGo HTML** (non-lite) result pages and merge outbound links (`NEWS_HTML_DISCOVERY_ENABLED`, cap `NEWS_HTML_DISCOVERY_MAX_TOTAL`). These rows often have **no** `published` time; the same calendar-window filter as RSS may **drop** them when you require strict dates — that is a deliberate tradeoff (see collector filter).

## What this codebase does now

1. **Google News RSS date chunking** — For windows longer than `NEWS_GOOGLE_CHUNK_THRESHOLD_DAYS` (default 90), the same base query is re-run with `after:YYYY-MM-DD before:YYYY-MM-DD` slices so Google is less likely to return only the most recent tail. Tune `NEWS_GOOGLE_CHUNK_DAYS` and `NEWS_GOOGLE_MAX_CHUNKS`.
2. **Extra query variants** — Additional Google phrases plus `site:moneycontrol.com` / ET / Business Standard style filters.
3. **Optional NewsAPI.org** — Set `NEWSAPI_API_KEY` to pull English `everything` results into the same merge/dedupe path (subject to [NewsAPI](https://newsapi.org/) plan limits; free developer tier may restrict how far back `from` can go).
4. **Configurable RSS** — `PEAD_NEWS_EXTRA_RSS_FEEDS` for more feeds you are allowed to poll.

## Practical expectations

- **SME / thin names** may still show **dozens** of items, not hundreds, even with chunking — there may simply not be more indexed English articles.
- **Regulatory / exchange notices** often do not appear as “news” in Google; consider a **separate announcements pipeline** (NSE APIs / scraping) if you need filing-grade density.
- For **true** production density, budget for a **licensed** feed or **NewsAPI** paid tier and entity-level dedupe downstream.

## Environment summary

| Variable | Purpose |
|----------|---------|
| `NEWSAPI_API_KEY` | Optional NewsAPI.org `everything` fetch |
| `NEWSAPI_MAX_RESULTS` | Cap merged NewsAPI rows (default 80) |
| `NEWS_GOOGLE_CHUNK_THRESHOLD_DAYS` | Start chunking when window span exceeds this |
| `NEWS_GOOGLE_CHUNK_DAYS` | Length of each `after:`/`before:` slice |
| `NEWS_GOOGLE_MAX_CHUNKS` | Safety cap on RSS round-trips per query |
| `PEAD_NEWS_EXTRA_RSS_FEEDS` | Comma-separated RSS URLs |
