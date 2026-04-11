"""
SQLite persistence for chat sessions and turns (user + assistant + optional tool trace).

Used by FastAPI chat endpoints; path from ``CONFIG["CHAT_SQLITE_PATH"]``.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatStore:
    def __init__(self, path: str):
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT DEFAULT 'chat'
                );
                CREATE TABLE IF NOT EXISTS chat_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_content TEXT NOT NULL,
                    assistant_content TEXT,
                    tool_trace_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session ON chat_turns(session_id);
                """
            )

    def has_session(self, session_id: str) -> bool:
        with self._conn() as c:
            r = c.execute(
                "SELECT 1 FROM chat_sessions WHERE id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        return r is not None

    def ensure_session(self, session_id: str, source: str = "chat") -> None:
        now = _utc_now()
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO chat_sessions (id, created_at, updated_at, source)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (session_id, now, now, source),
            )

    def touch_session(self, session_id: str) -> None:
        now = _utc_now()
        with self._conn() as c:
            c.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    def append_turn_user(self, session_id: str, user_content: str) -> int:
        now = _utc_now()
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO chat_turns (session_id, user_content, assistant_content, created_at, updated_at)
                VALUES (?, ?, NULL, ?, ?)
                """,
                (session_id, user_content, now, now),
            )
            return int(cur.lastrowid)

    def complete_turn(
        self,
        turn_id: int,
        assistant_content: Optional[str],
        tool_trace_json: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        now = _utc_now()
        with self._conn() as c:
            c.execute(
                """
                UPDATE chat_turns
                SET assistant_content = ?, tool_trace_json = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (assistant_content, tool_trace_json, error, now, turn_id),
            )
            c.execute(
                """
                UPDATE chat_sessions SET updated_at = ?
                WHERE id = (SELECT session_id FROM chat_turns WHERE id = ?)
                """,
                (now, turn_id),
            )

    def insert_complete_turn(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        tool_trace_json: Optional[str] = None,
        error: Optional[str] = None,
    ) -> int:
        """Non-streaming: one row with both sides."""
        self.ensure_session(session_id)
        now = _utc_now()
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO chat_turns (session_id, user_content, assistant_content, tool_trace_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_content,
                    assistant_content,
                    tool_trace_json,
                    error,
                    now,
                    now,
                ),
            )
            tid = int(cur.lastrowid)
            c.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            return tid

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT s.id, s.created_at, s.updated_at, s.source,
                       COUNT(t.id) AS turn_count,
                       MAX(t.created_at) AS last_turn_at
                FROM chat_sessions s
                LEFT JOIN chat_turns t ON t.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session_turns(self, session_id: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT id, session_id, user_content, assistant_content, tool_trace_json, error, created_at, updated_at
                FROM chat_turns
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("tool_trace_json"):
                try:
                    d["tool_trace"] = json.loads(d["tool_trace_json"])
                except json.JSONDecodeError:
                    d["tool_trace"] = None
            del d["tool_trace_json"]
            out.append(d)
        return out


def accumulate_stream_line(
    line_json: str,
    *,
    text_acc: List[str],
    tool_events: List[Dict[str, Any]],
    final_from_done: List[Optional[str]],
    error_out: List[Optional[str]],
) -> None:
    """Parse one NDJSON line from ``stream_research_chat`` for persistence."""
    try:
        d = json.loads(line_json)
    except json.JSONDecodeError:
        return
    t = d.get("type")
    if t == "text_delta" and d.get("content"):
        text_acc.append(str(d["content"]))
    elif t == "tool_call":
        tool_events.append(
            {
                "kind": "tool_call",
                "tool_name": d.get("tool_name"),
                "args": d.get("args"),
                "tool_call_id": d.get("tool_call_id"),
            }
        )
    elif t == "tool_result":
        tool_events.append(
            {
                "kind": "tool_result",
                "tool_call_id": d.get("tool_call_id"),
                "content_preview": d.get("content_preview"),
            }
        )
    elif t == "done":
        out = d.get("output")
        if isinstance(out, str) and out.strip():
            final_from_done[0] = out
    elif t == "error":
        error_out[0] = str(d.get("message") or "error")
