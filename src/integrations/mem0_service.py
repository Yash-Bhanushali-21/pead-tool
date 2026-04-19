"""
Optional [Mem0](https://github.com/mem0ai/mem0) long-term memory for chat.

Disabled unless ``MEM0_ENABLED`` is true and ``OPENAI_API_KEY`` is set (Mem0 OSS defaults
use OpenAI for extraction and embeddings). Install: ``pip install mem0ai``.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from src.config.config import CONFIG

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_memory_singleton: Any = None  # None | False | Memory instance


def mem0_runtime_enabled() -> bool:
    if not bool(CONFIG.get("MEM0_ENABLED", False)):
        return False
    if not (str(CONFIG.get("OPENAI_API_KEY", "") or "").strip()):
        return False
    try:
        import mem0  # noqa: F401  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("mem0ai not installed; Mem0 disabled.")
        return False
    return True


def _get_memory():
    """Lazy singleton; returns None if Mem0 unavailable or init failed."""
    global _memory_singleton
    if not mem0_runtime_enabled():
        return None
    with _lock:
        if _memory_singleton is None:
            try:
                from mem0 import Memory

                _memory_singleton = Memory()
            except Exception as e:
                logger.warning("Mem0 Memory() init failed (%s); continuing without Mem0.", e)
                _memory_singleton = False
        if _memory_singleton is False:
            return None
        return _memory_singleton


def resolve_mem0_user_id(mem0_user_id: Optional[str], session_id: Optional[str]) -> str:
    """Prefer explicit client id, else SQLite session id, else default env/local."""
    u = (mem0_user_id or "").strip()
    if u:
        return u
    s = (session_id or "").strip()
    if s:
        return s
    d = str(CONFIG.get("MEM0_DEFAULT_USER_ID") or "local").strip()
    return d or "local"


def format_mem0_block(user_id: str, query: str) -> Optional[str]:
    """Return a short plain-text block for the coordinator, or None."""
    m = _get_memory()
    if not m or not (user_id or "").strip() or not (query or "").strip():
        return None
    try:
        top_k = int(CONFIG.get("MEM0_TOP_K", 5))
        try:
            out = m.search(query, filters={"user_id": user_id.strip()}, top_k=top_k)
        except TypeError:
            out = m.search(query, filters={"user_id": user_id.strip()}, limit=top_k)
        results = (out or {}).get("results") or []
        if not results:
            return None
        lines: List[str] = []
        for r in results:
            if isinstance(r, dict):
                txt = r.get("memory")
            else:
                txt = getattr(r, "memory", None)
            if txt:
                lines.append(f"- {txt}")
        if not lines:
            return None
        return (
            "Retrieved long-term notes (Mem0; may be stale — verify with tools; "
            "not live market data):\n" + "\n".join(lines)
        )
    except Exception as e:
        logger.warning("Mem0 search failed: %s", e)
        return None


def mem0_add_turn(user_id: str, user_message: str, assistant_message: str) -> None:
    """Persist this exchange into Mem0 (best-effort)."""
    m = _get_memory()
    if not m or not (user_id or "").strip():
        return
    um = (user_message or "").strip()
    am = (assistant_message or "").strip()
    if not um or not am:
        return
    try:
        messages: List[Dict[str, str]] = [
            {"role": "user", "content": um[:120_000]},
            {"role": "assistant", "content": am[:120_000]},
        ]
        m.add(messages, user_id=user_id.strip())
    except Exception as e:
        logger.warning("Mem0 add failed: %s", e)
