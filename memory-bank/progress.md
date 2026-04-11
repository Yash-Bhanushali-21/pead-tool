# Progress

## What works

- PEAD pipeline, scoring, CLI and tooling (see README).
- FastAPI: tool routes, streaming chat with SQLite session persistence.
- Web: Chat (`/`) with SSE streaming, Markdown after stream, session sidebar, mobile drawer + desktop collapse, scroll tuned for streaming + “Jump to latest”.
- Tools hub and tool pages under `/tools`.
- **Docs / process:** `memory-bank/` (six core files), `PROJECT_MEMORY.md` (changelog + README snapshot source), `scripts/sync_memory_readme.py`, `.cursor/rules/memory-bank.mdc`.

## Known gaps / backlog

- Open items: see `activeContext.md` and `PROJECT_MEMORY.md` → Open questions.
- Large JS bundle on chat route (markdown stack); optional code-splitting later.

## Milestone mirror (high level)

Canonical table: **`PROJECT_MEMORY.md` → Change log** (append-only, newest first).

| Date (UTC) | Note |
|------------|------|
| 2026-04-12 | Full Memory Bank review; `activeContext` + `progress` refreshed; documented **session continuity** (read `memory-bank/*.md` at task start; `@` mention when user wants guaranteed load). |
| 2026-04-11 | Memory Bank workflow introduced; `memory-bank.mdc`; merged old `00-project-memory.mdc`. |

For full history see **`PROJECT_MEMORY.md`**.
