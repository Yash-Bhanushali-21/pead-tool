# PEAD Tool - Post-Earnings Announcement Drift Analysis

<!-- MEMORY_SNAPSHOT_START -->

> **Living context:** Read all **`memory-bank/*.md`** at task start (Cursor rule `memory-bank.mdc`). Dated **change log** and README snapshot source: [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md).
> - **Memory Bank:** Durable context in `memory-bank/` (read all `.md` there at task start); Cursor rule `.cursor/rules/memory-bank.mdc` (always apply). This file remains the **change log** + **README snapshot** source.
> - **News layer:** Optional article **scraping** (trafilatura) + metadata; aggregate **bullish/bearish/neutral** media stance; optional final OpenAI **`ai_digest`** (toggle per run on equity single + `/api/tools/run/news` + agent tool). **`articles_preview`** uses dated-then-undated ordering so HTML discovery / undated rows are not dropped under tight preview caps; citations rows carry **`collector_source`** / **`body_scrape_present`** in metadata.
> - **Stack:** Python PEAD pipeline (NSE/Yahoo), FastAPI (`server/`), PydanticAI agents (`src/agent/`), React + Vite + Tailwind (`web/`).
> - **Entry:** CLI `main.py` (PEAD modes: recent / single / batch); dev **`./scripts/dev.sh`** (venv-aware `uvicorn` + `web/` Vite) or repo-root **`npm run dev`** (concurrently: API + Vite); UI **`/`** (chat) and **`/tools`** (unified equity-research tool; legacy `/tools/*` paths redirect here).
> - **Config:** `src/config/config.py` / `src/config/settings.py`, `.env` via `python-dotenv`; **`OPENAI_API_KEY`** required for **chat** and any tool path that calls OpenAI (e.g. news LLM / `ai_digest`, research desk, optional technical verdict). Plain data-only tool calls can run without it.
> - **Memory sync:** After editing this section, run `python3 scripts/sync_memory_readme.py` or manually update the README block between `MEMORY_SNAPSHOT` markers.
> - **Time:** Event anchors use `src/utils/time_compat.py` (naive UTC) so API/feed timestamps never trip pandas tz-naive vs tz-aware comparisons.
> - **Trade readiness:** `src/trade_context/` adds execution-context scoring (not a trade recommendation); folded into synthesis blend when present.

<!-- MEMORY_SNAPSHOT_END -->

This repository is a **research stack** for **NSE-listed** names: classic **PEAD** (event-study windows, CARs, composite scoring), plus a **FastAPI** surface, **React** tools UI, **news/sentiment** collection (RSS, search, optional HTML discovery, optional article scrape), **trade-context** metrics, and an optional **PydanticAI** chat agent. Outputs are for **research and tooling only** — not investment advice.

## Overview

**PEAD (Post-Earnings Announcement Drift)** is the empirical pattern that prices can drift after earnings surprises. The Python core estimates a market model, builds abnormal and cumulative abnormal returns, and combines **five scored pillars** into a 0–100 composite (see `src/scoring/`).

**Equity research (calendar window)** — the path used by **`POST /api/tools/run/single`** and the **`/tools`** page — runs a **shared date range** for OHLCV, technicals (with chart payload where configured), **symbol-scoped news**, optional **broader market-context headlines**, **trade readiness**, optional **research desk** LLM synthesis, and on-disk JSON/artifacts when `output_dir` is set. Pipeline stages are selectable in the UI/API.

**CLI (`main.py`)** still supports **recent**, **single-announcement**, and **batch** PEAD runs for users who prefer the command line.

## Features (summary)

| Area | What you get |
|------|----------------|
| **PEAD core** | Market model (OLS), AR/CAR windows, significance tests, composite score + rating (`src/pead/`, `src/models/`, `src/scoring/`) |
| **Data** | NSE + Yahoo (+ optional `jugaad-data` path); caching via `DataManager` |
| **News** | Headline collection, optional **trafilatura** body scrape, TextBlob + optional OpenAI headline blend, optional final **`ai_digest`**; SQLite **citations** (`GET /api/news/articles`) |
| **API** | FastAPI: **`/api/tools/*`**, **`/api/chat/stream`**, health, chat sessions — see [API & web](#api--web) |
| **Web** | Vite + React + Tailwind: **`/`** chat, **`/tools`** unified equity research (legacy `/tools/news` etc. redirect here) |
| **Agent** | PydanticAI coordinator + tools calling `PEADAnalyzer` and news/fundamentals/technical helpers (`src/agent/`) |

## Quick start

```bash
git clone <repository-url>
cd pead-tool
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cd web && npm install && cd ..
```

**Environment:** copy `.env.sample` → `.env` if present, or set at least **`OPENAI_API_KEY`** for chat and any OpenAI-backed tool steps (news LLM / `ai_digest`, research desk, optional technical verdict). Data-only runs (e.g. fundamentals without LLM) may work without it.

**Run API + web together** (default ports **8000** / **5173**; override with `UVICORN_PORT` / `VITE_PORT` for `scripts/dev.sh`):

```bash
./scripts/dev.sh    # or: make dev
```

Alternative from repo root (uses root `devDependencies` **concurrently**):

```bash
npm install && npm run dev
```

**Manual split** (two terminals):

```bash
# Terminal 1 — API (uses .venv/bin/python if present)
.venv/bin/python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — UI (proxies /api → backend; see web/vite.config.ts)
cd web && npm run dev
```

Open **`http://localhost:5173`**. Only the UI port is for humans in dev; the API is on **8000** unless you change it.

### Chat (PydanticAI + Mem0)

- **Coordinator** streams replies and calls tools (`PEADAnalyzer`, news, calendar, etc.).
- **Research desk** (when enabled) adds consolidated narrative — requires `OPENAI_API_KEY`.

**Optional Mem0:** `MEM0_ENABLED=true` after `pip install` (see `requirements.txt`). Scope by chat `session_id` or `mem0_user_id` / `MEM0_DEFAULT_USER_ID`. Per request: `use_mem0: false`. **`GET /api/health`** exposes `mem0_enabled` / `mem0_runtime`.

## API & web

| Surface | Notes |
|---------|--------|
| **`/`** | Chat UI; **`POST /api/chat/stream`** (SSE), **`POST /api/chat`** |
| **`/tools`** | Single **equity research** form: symbol, **inclusive YYYY-MM-DD range**, pipeline stage toggles, optional **`include_symbol_news_ai_digest` / `include_market_news_ai_digest`** (skip final OpenAI digest while testing) |
| **Legacy routes** | `/tools/news`, `/tools/technical`, … → **redirect to `/tools`** (`web/src/App.tsx`) |
| **`GET /api/tools/config`** | Defaults for news, CLI hints, pipeline stage ids |
| **`POST /api/tools/run/single`** | Full equity research for one symbol + date range |
| **Other `POST /api/tools/run/*`** | `recent`, `fundamentals`, `technical`, `news`, `scoring`, `trade-readiness`, `document-pdf`, `execution-snapshot`, `yahoo-calendar` — see `server/tools_routes.py` |
| **`GET /api/news/articles`** | Citations rows from SQLite (`fetched_date` UTC, optional `symbol`) — `server/news_routes.py` |

**OpenAI usage:** Chat always expects a key when using the agent. **`run/single`** and related routes only need a key when a selected stage invokes an LLM (news synthesis / `ai_digest`, research desk, technical AI verdict). Pure fundamentals/scoring/data steps can run without it.

## Dependencies

Pinned in **`requirements.txt`**. Highlights:

- **Core quant:** numpy, pandas, scipy, statsmodels, scikit-learn, yfinance, `nse`, `jugaad-data`, requests, beautifulsoup4  
- **Documents:** PyPDF2, pdfplumber  
- **Plots / reports:** matplotlib, seaborn, tabulate, tqdm  
- **News:** feedparser, textblob, trafilatura  
- **API & agent:** fastapi, uvicorn, openai, pydantic-ai, python-dotenv, mem0ai  

Frontend: **`web/package.json`** (React 18, Vite, Tailwind, lightweight-charts where used).

## Usage

### CLI (`main.py`)

```bash
python main.py --mode recent --top 10
python main.py --mode recent --top 10 --output ./results
python main.py --mode recent --top 5 --no-cache

python main.py --mode single --symbol RELIANCE --date 2024-01-15
python main.py --mode batch --file stocks.csv

python main.py --mode recent --top 10 --verbose
python main.py --mode recent --top 10 --no-visualize
python main.py --help
```

For **calendar-window equity research** (same model as the web tool), use the **HTTP API** (`POST /api/tools/run/single`) or the **`/tools`** UI — not a separate `main.py` subcommand.

### HTTP API

Use **`GET /api/tools/config`** for defaults, then **`POST /api/tools/run/single`** with JSON body (`symbol`, `range_start`, `range_end`, stage toggles, optional `news_max_articles`, `include_symbol_news_ai_digest`, `include_market_news_ai_digest`, etc.). See **`server/tools_routes.py`** and OpenAPI at **`/docs`** when the server is running.

## Repository layout

```
pead-tool/
├── main.py                      # CLI: recent / single / batch PEAD
├── server/                      # FastAPI: app, tools_routes, chat, news citations
├── web/                         # Vite + React (Chat + /tools)
├── scripts/dev.sh               # API + Vite (venv-aware Python)
├── src/
│   ├── analysis/pead_analyzer.py           # Orchestrator: CLI + equity research entry
│   ├── equity_research_pipeline/           # Windowed multi-stage pipeline
│   ├── pead/, models/, scoring/            # Event study + composite score
│   ├── data/                               # NSE / Yahoo / cache (DataManager)
│   ├── news/                               # Collector, sentiment, scrape, citations preview
│   ├── agent/                              # PydanticAI coordinator + tools
│   ├── fundamentals/, technical/, trade_context/
│   ├── documents/                          # PDF download / parse
│   ├── persistence/                        # Chat + news SQLite helpers
│   └── config/                             # config.py, settings.py
├── memory-bank/               # Durable project context (read by agents)
├── PROJECT_MEMORY.md          # Changelog + README snapshot source
├── issues-to-fix/             # Ad-hoc backlog notes (optional)
├── requirements.txt
└── README.md
```

## Configuration

- **Environment:** `.env` (see `.env.sample` if provided) loaded via **`python-dotenv`**; many keys are read through **`src/config/config.py`**.  
- **Python defaults:** **`src/config/settings.py`** — market model window, CAR windows, scoring weights, thresholds, cache paths.  
- **CORS:** `PEAD_CORS_ORIGINS` (comma-separated) for extra browser origins in dev.  
- **SQLite:** `CHAT_SQLITE_PATH` (chat sessions); news citations default to the same DB unless **`NEWS_SQLITE_PATH`** is set.  
- **News tuning:** e.g. `NEWS_HTML_DISCOVERY_ENABLED`, `NEWSAPI_API_KEY`, model names — surfaced in **`GET /api/tools/config`** where applicable.

## Methodology

### Market Model
```
R_stock,t = α + β * R_market,t + ε_t
```
- Estimated using OLS on 120 trading days before announcement
- Used to calculate expected returns

### Abnormal Returns
```
AR_t = R_stock,t - (α + β * R_market,t)
```
- Daily abnormal return = actual return - expected return

### Cumulative Abnormal Returns
```
CAR(t1, t2) = Σ AR_t for t in [t1, t2]
```
- Sum of abnormal returns over window
- Statistical significance tested using t-tests

### Composite Score
```
Score = Σ (Normalized_Component_i * Weight_i)
```
- Each component normalized to 0-100 scale
- Weighted sum using configured weights
- Final score 0-100 with rating assignment

## Output Example

CLI-style text report (shape varies by mode). **Ratings** (e.g. BUY / SELL strings) are **internal composite labels**, not trade instructions.

```
================================================================================
PEAD COMPOSITE SCORE REPORT
================================================================================

COMPOSITE SCORE: 73.45/100
RATING: BUY
CONFIDENCE: 85%

------------------------------------------------------------------------------

COMPONENT BREAKDOWN:

Earnings Surprise:
  Raw Score:             52.00
  Normalized (0-100):    74.29
  Weight:                25.0%
  Contribution:          18.57

Price Reaction:
  Raw Score:             14.00
  Normalized (0-100):    70.00
  Weight:                20.0%
  Contribution:          14.00

...

------------------------------------------------------------------------------

RECOMMENDATION:
STRONG PEAD SIGNAL - Score: 73.5/100. High probability of continued drift
in announcement direction. Consider entry for 30-60 day horizon.

================================================================================
```

## Performance Considerations

- **Caching**: All data fetched is cached (default 7 days TTL)
- **Parallel Fetching**: Independent data sources fetched concurrently
- **Fallback Logic**: Automatic fallback from NSE to Yahoo Finance
- **Error Handling**: Graceful degradation with partial data

## Limitations & Future Enhancements

### Current Limitations
- PDF parsing quality depends on document format
- Historical earnings consensus not available (using YoY/QoQ instead)
- Limited corporate governance data integration

### Planned Enhancements
- [ ] Backtesting framework with historical performance
- [ ] Portfolio construction with multiple signals
- [ ] Real-time monitoring and alerts
- [ ] Integration with trading APIs
- [ ] Machine learning model for score optimization
- [ ] More comprehensive fundamental data (Screener.in, etc.)

## Academic References

PEAD is well-documented in finance literature:

1. Ball, R., & Brown, P. (1968). "An Empirical Evaluation of Accounting Income Numbers"
2. Bernard, V., & Thomas, J. (1989). "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?"
3. Chan, L. K., Jegadeesh, N., & Lakonishok, J. (1996). "Momentum Strategies"

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit pull request

## Support

Open an issue on the project tracker with repro steps (CLI command, API payload, or UI path) and environment (Python version, OS).

## Disclaimer

This software is for **education and research** only. It is **not** investment, legal, or tax advice. Composite labels and narrative text are **heuristic outputs** — validate against primary data and your own process before relying on them.

---

**Documentation:** Durable context lives in **`memory-bank/`**; dated changes in **[`PROJECT_MEMORY.md`](PROJECT_MEMORY.md)**. After editing the snapshot there, run **`python3 scripts/sync_memory_readme.py`** to refresh the quoted block at the top of this README.
