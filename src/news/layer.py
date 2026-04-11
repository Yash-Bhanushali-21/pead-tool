"""
Shared headline collection + sentiment pipeline (no PEAD) — used by /api/tools and chat agent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from src.analysis.pead_analyzer import PEADAnalyzer
from src.news import NewsCollector, run_news_sentiment_pipeline


def run_news_sentiment_layer(
    analyzer: PEADAnalyzer,
    symbol: str,
    *,
    lookback_days: int = 90,
    max_articles: int = 80,
    preview_limit: int = 40,
) -> Dict[str, Any]:
    """
    Yahoo/Google RSS headlines + TextBlob / optional OpenAI blend — same contract as
    ``POST /api/tools/run/news``.
    """
    sym = symbol.strip().upper()
    info = analyzer.data_manager.get_company_fundamentals(sym)
    company_name = (info.get("company_name") or sym).strip()
    coll = NewsCollector()
    articles = coll.collect(
        sym,
        company_name,
        datetime.now(),
        lookback_days=int(lookback_days),
        max_articles=int(max_articles),
    )
    ns = run_news_sentiment_pipeline(sym, company_name, articles)
    preview = []
    for a in articles[:preview_limit]:
        preview.append(
            {
                "title": a.title,
                "url": a.url,
                "published": a.published.isoformat() if a.published else None,
                "source": a.source,
                "summary": (a.summary or "")[:1200],
            }
        )
    return {
        "success": True,
        "symbol": sym,
        "article_count": len(articles),
        "articles_preview": preview,
        "news_sentiment": ns,
    }
