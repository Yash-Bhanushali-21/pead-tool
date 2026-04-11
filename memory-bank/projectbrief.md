# Project brief

**PEAD Tool** — Post-Earnings Announcement Drift analysis for **Indian (NSE) equities**.

## In scope

- Quantitative PEAD pipeline: market model, abnormal returns, CAR windows, composite scoring, reporting (`src/pead/`, CLI `main.py`).
- **Research agent layer:** PydanticAI multi-agent coordinator + tools calling PEAD, news/sentiment, fundamentals, technicals, etc. (`src/agent/`).
- **API:** FastAPI (`server/`) — streaming chat (`/api/chat/stream`), tool routes (`/api/tools/*`), CORS for the web UI.
- **Web UI:** React + Vite + Tailwind (`web/`) — chat at `/`, PEAD and other tools at `/tools/*`.

## Out of scope (for product positioning)

- Not investment advice; research and tooling only. Disclaimers belong in UX and agent tone (see `institutional-analyst-tone` rule).

## Source of truth

- **What “in scope” means:** this file + `productContext.md`.
- **Implementation status:** `progress.md`.
