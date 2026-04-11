"""
Shared headline collection + optional article scraping + sentiment pipeline (no PEAD) — used by /api/tools and chat agent.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.config import CONFIG
from src.news import NewsCollector, run_news_sentiment_pipeline
from src.news.article_scraper import enrich_articles_with_scrapes
from src.persistence.sqlite_news_articles import get_news_article_store

logger = logging.getLogger(__name__)


def run_news_sentiment_layer(
    analyzer: PEADAnalyzer,
    symbol: str,
    *,
    lookback_days: int = 90,
    max_articles: int = 80,
    preview_limit: int = 40,
    end_date: Optional[datetime] = None,
    scrape_bodies: bool = True,
    max_scrape: int = 25,
) -> Dict[str, Any]:
    """
    Yahoo/Google RSS headlines + optional full-page scrape (trafilatura) + TextBlob / optional OpenAI blend.

    ``end_date`` defaults to now; window is [end_date - lookback_days, end_date].

    ``max_scrape`` caps how many article URLs are fetched for body text (0 = skip scraping).
    """
    sym = symbol.strip().upper()
    info = analyzer.data_manager.get_company_fundamentals(sym)
    company_name = (info.get("company_name") or sym).strip()
    coll = NewsCollector()
    end = end_date or datetime.now()
    articles = coll.collect(
        sym,
        company_name,
        end,
        lookback_days=int(lookback_days),
        max_articles=int(max_articles),
    )

    scrape_stats: Dict[str, Any] = {"attempted": 0, "bodies_ok": 0, "skipped": not scrape_bodies}
    if scrape_bodies and max_scrape > 0 and articles:
        scrape_stats["attempted"] = min(len(articles), int(max_scrape))
        enrich_articles_with_scrapes(articles, max_scrape=int(max_scrape))
        scrape_stats["bodies_ok"] = sum(1 for a in articles[: max_scrape] if (a.body_text or "").strip())
    else:
        scrape_stats["skipped"] = True

    ns = run_news_sentiment_pipeline(sym, company_name, articles)

    persisted_rows = 0
    try:
        db_path = CONFIG.get("NEWS_SQLITE_PATH") or CONFIG["CHAT_SQLITE_PATH"]
        store = get_news_article_store(db_path)
        persisted_rows = store.persist_fetch(sym, articles, ns.get("per_article") or [])
    except Exception as e:
        logger.warning("Persist news citations failed: %s", e)

    preview = []
    for a in articles[:preview_limit]:
        row: Dict[str, Any] = {
            "title": a.title,
            "url": a.url,
            "published": a.published.isoformat() if a.published else None,
            "source": a.source,
            "summary": (a.summary or "")[:1200],
        }
        if (a.body_text or "").strip():
            row["body_preview"] = (a.body_text[:900] + "…") if len(a.body_text) > 900 else a.body_text
            row["body_word_count"] = len(a.body_text.split())
        if a.scrape_metadata:
            row["page_metadata"] = {
                k: v
                for k, v in a.scrape_metadata.items()
                if k
                in (
                    "title",
                    "author",
                    "hostname",
                    "sitename",
                    "date",
                    "description",
                    "word_count",
                )
            }
        if a.scrape_error:
            row["scrape_error"] = a.scrape_error[:200]
        preview.append(row)

    return {
        "success": True,
        "symbol": sym,
        "window": {
            "end": end.isoformat(),
            "lookback_days": int(lookback_days),
        },
        "article_count": len(articles),
        "articles_preview": preview,
        "scrape": scrape_stats,
        "news_sentiment": ns,
        "persisted_citations": persisted_rows,
    }
