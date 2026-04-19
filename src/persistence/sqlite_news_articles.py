"""
SQLite persistence for news articles fetched/scraped by the news layer (citations DB).

Uses the same file as chat by default (``NEWS_SQLITE_PATH`` or ``CHAT_SQLITE_PATH``).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.news.collector import NewsArticle


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _json_safe_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure metadata is JSON-serializable for SQLite (trafilatura / scrapers may put lxml nodes
    or other opaque objects in nested structures).
    """

    def _safe(v: Any) -> Any:
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, datetime):
            try:
                if v.tzinfo is not None:
                    return v.astimezone(timezone.utc).isoformat()
                return v.isoformat()
            except Exception:
                return str(v)
        if isinstance(v, dict):
            return {str(k): _safe(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, set)):
            return [_safe(x) for x in v][:200]
        # lxml.etree._Element (tag + itertext); avoid importing lxml if unused
        if getattr(v, "tag", None) is not None and callable(getattr(v, "itertext", None)):
            try:
                return "".join(v.itertext())[:4000]
            except Exception:
                return str(v)[:4000]
        return str(v)[:8000]

    if not isinstance(meta, dict):
        return {}
    return _safe(meta)


class NewsArticleStore:
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
                CREATE TABLE IF NOT EXISTS news_article_citations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fetched_at TEXT NOT NULL,
                    fetched_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    article_published_at TEXT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT,
                    summary TEXT,
                    body_excerpt TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    scrape_ok INTEGER NOT NULL DEFAULT 0,
                    scrape_error TEXT,
                    polarity REAL,
                    stance TEXT,
                    UNIQUE(symbol, url, fetched_date)
                );
                CREATE INDEX IF NOT EXISTS idx_nac_fetched_date ON news_article_citations(fetched_date);
                CREATE INDEX IF NOT EXISTS idx_nac_symbol_date ON news_article_citations(symbol, fetched_date);
                """
            )

    def persist_fetch(
        self,
        symbol: str,
        articles: List[NewsArticle],
        per_article: List[Dict[str, Any]],
    ) -> int:
        """
        Store one row per article for this fetch. ``fetched_date`` is UTC calendar date (filter "today").

        Returns number of rows written/updated.
        """
        sym = symbol.strip().upper()
        fetched_at = _utc_now_iso()
        fetched_date = _utc_today_str()
        per_by_url = {row.get("url", ""): row for row in per_article}

        n = 0
        with self._conn() as c:
            for a in articles:
                extra = per_by_url.get(a.url, {})
                pub = a.published.isoformat() if a.published else None
                meta: Dict[str, Any] = dict(a.scrape_metadata or {})
                if extra.get("metadata"):
                    meta = {**meta, **(extra["metadata"] or {})}
                meta["collector_source"] = a.source
                meta["body_scrape_present"] = bool((a.body_text or "").strip())
                meta = _json_safe_metadata(meta)
                body_ex = (a.body_text or "")[:2000] if (a.body_text or "").strip() else None
                scrape_ok = 1 if extra.get("scrape_ok") else 0
                pol = extra.get("polarity")
                stance = extra.get("stance")
                c.execute(
                    """
                    INSERT INTO news_article_citations (
                        fetched_at, fetched_date, symbol, article_published_at,
                        url, title, source, summary, body_excerpt, metadata_json,
                        scrape_ok, scrape_error, polarity, stance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, url, fetched_date) DO UPDATE SET
                        fetched_at = excluded.fetched_at,
                        article_published_at = excluded.article_published_at,
                        title = excluded.title,
                        source = excluded.source,
                        summary = excluded.summary,
                        body_excerpt = excluded.body_excerpt,
                        metadata_json = excluded.metadata_json,
                        scrape_ok = excluded.scrape_ok,
                        scrape_error = excluded.scrape_error,
                        polarity = excluded.polarity,
                        stance = excluded.stance
                    """,
                    (
                        fetched_at,
                        fetched_date,
                        sym,
                        pub,
                        a.url,
                        a.title,
                        a.source,
                        (a.summary or "")[:4000],
                        body_ex,
                        json.dumps(meta, ensure_ascii=False, allow_nan=False),
                        scrape_ok,
                        (a.scrape_error or extra.get("scrape_error"))[:2000]
                        if (a.scrape_error or extra.get("scrape_error"))
                        else None,
                        pol,
                        stance,
                    ),
                )
                n += 1
        return n

    def list_by_fetched_date(
        self,
        fetched_date: str,
        symbol: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """``fetched_date`` is YYYY-MM-DD (UTC)."""
        fd = fetched_date.strip()[:10]
        q = """
            SELECT id, fetched_at, fetched_date, symbol, article_published_at, url, title, source,
                   summary, body_excerpt, metadata_json, scrape_ok, scrape_error, polarity, stance
            FROM news_article_citations
            WHERE fetched_date = ?
        """
        args: List[Any] = [fd]
        if symbol:
            q += " AND symbol = ?"
            args.append(symbol.strip().upper())
        q += " ORDER BY fetched_at DESC, id DESC LIMIT ?"
        args.append(int(limit))
        with self._conn() as c:
            rows = c.execute(q, tuple(args)).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            meta = {}
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except json.JSONDecodeError:
                pass
            out.append(
                {
                    "id": r["id"],
                    "fetched_at": r["fetched_at"],
                    "fetched_date": r["fetched_date"],
                    "symbol": r["symbol"],
                    "article_published_at": r["article_published_at"],
                    "url": r["url"],
                    "title": r["title"],
                    "source": r["source"],
                    "summary": r["summary"],
                    "body_excerpt": r["body_excerpt"],
                    "metadata": meta,
                    "scrape_ok": bool(r["scrape_ok"]),
                    "scrape_error": r["scrape_error"],
                    "polarity": r["polarity"],
                    "stance": r["stance"],
                }
            )
        return out


_store: Optional[NewsArticleStore] = None


def get_news_article_store(sqlite_path: str) -> NewsArticleStore:
    """Singleton per path (call init_schema once from app lifespan)."""
    global _store
    if _store is None or _store.path != str(Path(sqlite_path).expanduser().resolve()):
        _store = NewsArticleStore(sqlite_path)
        _store.init_schema()
    return _store
