# Active context

**Last reviewed:** 2026-04-12 (full Memory Bank pass — user: “update memory bank”)

## Current focus

- **Memory Bank** is the structured brain: `memory-bank/*.md` + `.cursor/rules/memory-bank.mdc` (always apply).
- **Chat UI:** Session history sidebar (drawer mobile, collapsible rail desktop), stick-to-bottom scroll, **plain text while streaming** → **Markdown** after (`MarkdownContent`: react-markdown, remark-gfm, typography). App layout uses flex + `min-h-0` so the thread scrolls inside the viewport.
- **README / changelog:** `PROJECT_MEMORY.md` **Current snapshot** + **Change log**; sync to README via `scripts/sync_memory_readme.py`.

## Session continuity (for agents)

- **Start of substantive work:** Read **all** files under `memory-bank/` (not only this file) before planning or coding.
- **Always-apply rule** reminds every chat, but **file contents are not auto-loaded** into context until read or `@`-mentioned — so when in doubt, **read** `memory-bank/` or ask the user to attach `@memory-bank/activeContext.md` (and siblings if needed).
- User preference (confirmed): treat Memory Bank as **first** stop so active context is not lost across days.

## Recent decisions (stable)

- Chat persistence: `CHAT_SQLITE_PATH`; `/api/chat/sessions` for list + history.
- Time: `src/utils/time_compat.py` (naive UTC) to avoid pandas tz crashes.
- Trade readiness: `src/trade_context/` blended into synthesis when present; research-only disclaimers.

## Next steps (when relevant)

- After milestones: bump `progress.md`, append `PROJECT_MEMORY.md` change log, run `sync_memory_readme.py` if snapshot changes.
- Optional: code-split heavy chat client deps if bundle size hurts.

## Open questions

- (Track in `progress.md` / `PROJECT_MEMORY.md` backlog.)
