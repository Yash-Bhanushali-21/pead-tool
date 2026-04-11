"""
Collect news headlines/snippets for an Indian equity symbol from:
- Yahoo Finance ticker.news
- Google News RSS (public feeds; filter by date client-side)

Optional full-article text via ``article_scraper.enrich_articles_with_scrapes`` (trafilatura).
Default sentiment still works on title + snippet when bodies are not fetched.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus

import feedparser
import requests

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PEAD-Tool/1.0; +https://github.com/; research bot)"
)


def _to_utc_dt(x: Any) -> Optional[datetime]:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.replace(tzinfo=None) if x.tzinfo else x
    if isinstance(x, (int, float)) and x > 1e9:
        return datetime.utcfromtimestamp(x)
    return None


@dataclass
class NewsArticle:
    title: str
    url: str
    published: Optional[datetime]
    source: str
    summary: str = ""
    body_text: str = ""
    scrape_metadata: Dict[str, Any] = field(default_factory=dict)
    scrape_error: Optional[str] = None

    def text_for_sentiment(self) -> str:
        if (self.body_text or "").strip():
            # Cap very long bodies for lexicon speed; LLM gets separate capped list
            body = self.body_text.strip()
            if len(body) > 12000:
                body = body[:12000] + "…"
            return f"{self.title}. {body}".strip()
        return f"{self.title}. {self.summary}".strip()


class NewsCollector:
    """Fetch and dedupe news items within [end_date - lookback, end_date]."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    def collect(
        self,
        symbol: str,
        company_name: str,
        end_date: datetime,
        lookback_days: int = 90,
        max_articles: int = 80,
    ) -> List[NewsArticle]:
        start_date = end_date - timedelta(days=lookback_days)
        seen_urls: Set[str] = set()
        out: List[NewsArticle] = []

        out.extend(
            self._yahoo_news(symbol, start_date, end_date, seen_urls, max_articles)
        )
        time.sleep(0.4)
        out.extend(
            self._google_rss(
                symbol, company_name, start_date, end_date, seen_urls, max_articles
            )
        )

        out = [a for a in out if a.published is None or (start_date <= a.published <= end_date)]
        out.sort(key=lambda a: a.published or datetime.min, reverse=True)
        return out[:max_articles]

    def _yahoo_news(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        items: List[NewsArticle] = []
        try:
            import yfinance as yf

            ysym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
            t = yf.Ticker(ysym)
            raw = getattr(t, "news", None) or []
        except Exception as e:
            logger.warning(f"Yahoo news fetch failed: {e}")
            return items

        for n in raw:
            if len(items) >= cap:
                break
            url = n.get("link") or n.get("uuid") or ""
            if not url or url in seen:
                continue
            ts = n.get("providerPublishTime")
            pub = _to_utc_dt(ts)
            title = (n.get("title") or "").strip()
            if not title:
                continue
            summ = (n.get("summary") or "").strip()
            src = (n.get("publisher") or "Yahoo").strip()
            seen.add(url)
            items.append(
                NewsArticle(
                    title=title,
                    url=str(url),
                    published=pub,
                    source=src,
                    summary=summ,
                )
            )
        return items

    def _google_rss(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        items: List[NewsArticle] = []
        # Broad OR query; date filter applied after parse
        q = f"{company_name} OR {symbol}"
        url = (
            f"https://news.google.com/rss/search?q={quote_plus(q)}"
            f"&hl=en-IN&gl=IN&ceid=IN:en"
        )
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"Google News RSS parse failed: {e}")
            return items

        for e in getattr(parsed, "entries", []) or []:
            if len(items) + len(seen) >= cap * 2:
                break
            link = getattr(e, "link", "") or ""
            if not link or link in seen:
                continue
            title = (getattr(e, "title", "") or "").strip()
            if not title:
                continue
            summary = ""
            if hasattr(e, "summary"):
                summary = self._strip_html(e.summary)[:800]
            pub = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                try:
                    pub = datetime(*e.published_parsed[:6])
                except Exception:
                    pub = None
            elif hasattr(e, "updated_parsed") and e.updated_parsed:
                try:
                    pub = datetime(*e.updated_parsed[:6])
                except Exception:
                    pub = None
            seen.add(link)
            items.append(
                NewsArticle(
                    title=title,
                    url=link,
                    published=pub,
                    source="Google News",
                    summary=summary,
                )
            )
        return items

    @staticmethod
    def _strip_html(s: str) -> str:
        try:
            from bs4 import BeautifulSoup

            return BeautifulSoup(s, "html.parser").get_text(separator=" ", strip=True)
        except Exception:
            return s
