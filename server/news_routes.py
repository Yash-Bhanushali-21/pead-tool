"""
Read-only API for news article citations persisted by the news layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query

from src.config.config import CONFIG
from src.persistence.sqlite_news_articles import get_news_article_store

router = APIRouter(prefix="/api/news", tags=["news"])


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@router.get("/articles")
def list_news_citations(
    date: Optional[str] = Query(
        None,
        description="Filter by fetch date YYYY-MM-DD (UTC). Defaults to today.",
    ),
    symbol: Optional[str] = Query(None, description="Optional NSE symbol filter"),
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    """Rows stored when /api/tools/run/news completes — use ``fetched_date`` = day of fetch (UTC)."""
    d = (date or "").strip()[:10] or _utc_today()
    path = CONFIG.get("NEWS_SQLITE_PATH") or CONFIG["CHAT_SQLITE_PATH"]
    store = get_news_article_store(path)
    rows = store.list_by_fetched_date(d, symbol=symbol, limit=limit)
    return {
        "fetched_date_filter": d,
        "symbol_filter": symbol.strip().upper() if symbol else None,
        "count": len(rows),
        "articles": rows,
    }
