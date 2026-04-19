"""
Shared headline collection + optional article scraping + sentiment pipeline (no PEAD) — used by /api/tools and chat agent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.analysis.stock_analyzer import StockAnalyzer
from src.config.config import CONFIG
from src.news import NewsCollector, run_news_sentiment_pipeline
from src.news.article_preview import build_article_preview_rows
from src.news.article_scraper import enrich_articles_with_scrapes
from src.persistence.sqlite_news_articles import get_news_article_store

logger = logging.getLogger(__name__)


def run_news_sentiment_layer(
    analyzer: StockAnalyzer,
    symbol: str,
    *,
    lookback_days: int = 90,
    max_articles: int = 80,
    preview_limit: int = 56,
    end_date: Optional[datetime] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    scrape_bodies: bool = True,
    max_scrape: int = 32,
    include_ai_digest: bool = True,
) -> Dict[str, Any]:
    """
    Yahoo/Google RSS headlines + optional full-page scrape (trafilatura) + TextBlob / optional OpenAI blend.

    If ``window_start`` and ``window_end`` are set, articles are restricted to that **inclusive**
    datetime window (same semantics as equity-research OHLCV range). In that case ``lookback_days``
    is **ignored** (kept on the signature only for callers that use the rolling window mode).

    Otherwise ``end_date`` defaults to now and the window is ``[end_date - lookback_days, end_date]``.

    ``max_scrape`` caps how many article URLs are fetched for body text (0 = skip scraping).
    """
    sym = symbol.strip().upper()
    info = analyzer.data_manager.get_company_fundamentals(sym)
    company_name = (info.get("company_name") or sym).strip()
    coll = NewsCollector()
    if window_start is not None and window_end is not None:
        start = window_start
        end = window_end
    else:
        end = end_date or datetime.now()
        start = end - timedelta(days=int(lookback_days))
    articles = coll.collect(
        sym,
        company_name,
        start,
        end,
        max_articles=int(max_articles),
    )

    scrape_stats: Dict[str, Any] = {"attempted": 0, "bodies_ok": 0, "skipped": not scrape_bodies}
    if scrape_bodies and max_scrape > 0 and articles:
        scrape_stats["attempted"] = min(len(articles), int(max_scrape))
        enrich_articles_with_scrapes(articles, max_scrape=int(max_scrape))
        scrape_stats["bodies_ok"] = sum(1 for a in articles[: max_scrape] if (a.body_text or "").strip())
    else:
        scrape_stats["skipped"] = True

    ns = run_news_sentiment_pipeline(sym, company_name, articles, include_ai_digest=include_ai_digest)

    persisted_rows = 0
    try:
        db_path = CONFIG.get("NEWS_SQLITE_PATH") or CONFIG["CHAT_SQLITE_PATH"]
        store = get_news_article_store(db_path)
        persisted_rows = store.persist_fetch(sym, articles, ns.get("per_article") or [])
    except Exception as e:
        logger.warning("Persist news citations failed: %s", e)

    preview = build_article_preview_rows(articles, int(preview_limit))

    window_meta: Dict[str, Any] = {"start": start.isoformat(), "end": end.isoformat()}
    if window_start is None or window_end is None:
        window_meta["lookback_days"] = int(lookback_days)
    return {
        "success": True,
        "symbol": sym,
        "window": window_meta,
        "article_count": len(articles),
        "articles_preview": preview,
        "scrape": scrape_stats,
        "news_sentiment": ns,
        "persisted_citations": persisted_rows,
    }
