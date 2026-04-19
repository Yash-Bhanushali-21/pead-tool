# Product context

## Why this exists

Analysts and researchers need **repeatable, explainable PEAD-style analysis** on NSE symbols with optional **AI-assisted interpretation** (coordinator agent, desk-style synthesis) while keeping boundaries clear (research-only).

## Problems solved

- Run PEAD and related scans without ad-hoc notebooks only.
- Combine structured tool output (earnings windows, CAR, news/sentiment, technical context) with narrative synthesis when requested.
- Persist chat sessions (local SQLite) for continuity across turns.

## UX goals

- **Chat:** Streamed replies, readable Markdown after completion, stable scroll while streaming (plain text during token stream), session history sidebar (collapsible on desktop).
- **Tools:** Direct access to PEAD and auxiliary tools without always going through chat. Equity single run exposes optional switches (e.g. **skip final news `ai_digest`**) for faster/cheaper testing when iterating on collection or citations.
- **Tone:** Institutional analyst style where applicable; not retail hype (see `.cursor/rules/institutional-analyst-tone.mdc`).

## Users

- Internal research / power users comfortable with symbols, windows, and tool JSON.

## Cross-session use (Cursor)

- Durable project context lives in **`memory-bank/`**; agents should **read those files** at the start of non-trivial tasks. Users can **`@memory-bank`** (or specific files) in a new chat to guarantee that content is loaded.
