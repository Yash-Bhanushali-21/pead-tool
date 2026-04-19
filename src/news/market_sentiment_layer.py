"""
Broader **market-context** headlines (India / Nifty / sector) in the same calendar window as equity research.

Research-only: same caveats as ``run_news_sentiment_layer`` (RSS/HTML snippets, incomplete vs filings).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Set

from src.analysis.pead_analyzer import PEADAnalyzer
from src.news.collector import NewsArticle, NewsCollector
from src.news.article_preview import build_article_preview_rows
from src.news.article_scraper import enrich_articles_with_scrapes
from src.news.sentiment_pipeline import run_news_sentiment_pipeline
from src.persistence.sqlite_news_articles import get_news_article_store
from src.config.config import CONFIG

logger = logging.getLogger(__name__)


def run_market_sentiment_layer(
    analyzer: PEADAnalyzer,
    symbol: str,
    company_name: str,
    *,
    window_start: datetime,
    window_end: datetime,
    max_articles: int = 40,
    preview_limit: int = 40,
    scrape_bodies: bool = False,
    max_scrape: int = 12,
    include_ai_digest: bool = True,
) -> Dict[str, Any]:
    """
    Pull cross-sectional market headlines (Nifty, India equities, symbol sector context) and run
    the same sentiment pipeline used for symbol-scoped news.
    """
    sym = symbol.strip().upper()
    coll = NewsCollector()
    seen: Set[str] = set()
    merged: List[NewsArticle] = []

    queries_rss = [
        f"Nifty 50 India stock market {window_start.year}",
        "Indian stock market NSE equities outlook",
        f"{sym} India sector stock news",
        "RBI policy India markets equities",
        "FII DII flows Indian stock market",
        "India crude oil rupee impact stock market",
        "BSE Sensex India market news",
    ]
    per_q = max(6, max_articles // max(4, len(queries_rss)))
    for q in queries_rss:
        merged.extend(
            coll.rss_google_query(
                q, window_start, window_end, seen, per_q, source_label="Market (Google)"
            )
        )
        time.sleep(0.32)
    merged.extend(coll.bing_news_query(sym, company_name or sym, window_start, window_end, seen, max_articles))
    time.sleep(0.32)
    for bq in (
        "Nifty 50 India outlook",
        "Indian equities macro news",
        f"{sym} sector India stocks",
    ):
        merged.extend(
            coll.bing_news_query_raw(
                bq, window_start, window_end, seen, max(6, max_articles // 4), source_label="Market (Bing)"
            )
        )
        time.sleep(0.28)
    merged.extend(
        coll.duckduckgo_lite_query(
            sym, company_name or sym, window_start, window_end, seen, max(4, max_articles // 5)
        )
    )
    time.sleep(0.32)
    merged.extend(
        coll.html_discovery_articles(
            sym,
            company_name or sym,
            seen,
            max_total=min(16, max(8, max_articles // 2)),
        )
    )
    time.sleep(0.3)
    merged.extend(
        coll.collect_from_extra_rss_market(
            window_start, window_end, seen, max(12, max_articles // 2)
        )
    )

    merged = [a for a in merged if a.published is None or (window_start <= a.published <= window_end)]
    merged.sort(key=lambda a: a.published or datetime.min, reverse=True)
    articles = merged[: int(max_articles)]

    scrape_stats: Dict[str, Any] = {"attempted": 0, "bodies_ok": 0, "skipped": not scrape_bodies}
    if scrape_bodies and max_scrape > 0 and articles:
        scrape_stats["attempted"] = min(len(articles), int(max_scrape))
        enrich_articles_with_scrapes(articles, max_scrape=int(max_scrape))
        scrape_stats["bodies_ok"] = sum(
            1 for a in articles[:max_scrape] if (a.body_text or "").strip()
        )
    else:
        scrape_stats["skipped"] = True

    ns = run_news_sentiment_pipeline(
        sym, f"{company_name} (market context)", articles, include_ai_digest=include_ai_digest
    )

    persisted_rows = 0
    try:
        db_path = CONFIG.get("NEWS_SQLITE_PATH") or CONFIG["CHAT_SQLITE_PATH"]
        store = get_news_article_store(db_path)
        persisted_rows = store.persist_fetch(f"{sym}_MARKETCTX", articles, ns.get("per_article") or [])
    except Exception as e:
        logger.warning("Persist market-sentiment citations failed: %s", e)

    preview = build_article_preview_rows(articles, int(preview_limit))

    # ``run_news_sentiment_pipeline`` sets ``stock_media_stance`` to a string label, not a dict.
    raw_stance = ns.get("stock_media_stance") if isinstance(ns, dict) else None
    if isinstance(raw_stance, dict):
        label = str(raw_stance.get("label") or "neutral")
    elif isinstance(raw_stance, str) and raw_stance.strip():
        label = raw_stance.strip()
    else:
        label = "neutral"
    score = ns.get("news_score_0_100")
    rationale_parts = [
        f"**Headline stance (tool):** {label}.",
        f"**Articles in window:** {len(articles)} (Google multi-query, Bing, DDG-lite, optional RSS feeds from config; not exhaustive).",
    ]
    if isinstance(score, (int, float)):
        rationale_parts.append(f"**Heuristic news score (0–100):** {float(score):.1f} (same lexicon/LLM blend as symbol news — not a market-timing signal).")
    if ns.get("mean_polarity") is not None:
        rationale_parts.append(f"**Mean TextBlob polarity:** {float(ns['mean_polarity']):.3f} (snippet/title bias; verify with primary sources).")
    rationale = "\n\n".join(rationale_parts)

    return {
        "success": True,
        "kind": "market_sentiment",
        "symbol": sym,
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "article_count": len(articles),
        "articles_preview": preview,
        "scrape": scrape_stats,
        "market_sentiment": ns,
        "rationale_markdown": rationale,
        "persisted_citations": persisted_rows,
    }
