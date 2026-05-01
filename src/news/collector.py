"""
Collect news headlines/snippets for an Indian equity symbol from:
- Yahoo Finance ``ticker.news``
- Google News RSS (multiple query variants + India locale)
- Bing News RSS
- DuckDuckGo lite HTML (best-effort)
- Built-in India financial RSS feeds (NDTV Profit, Mint, Business Standard, etc.)
- Optional extra RSS feeds (``PEAD_NEWS_EXTRA_RSS_FEEDS`` / ``NEWS_EXTRA_RSS_FEEDS``), filtered to the symbol/company

Optional full-article text via ``article_scraper.enrich_articles_with_scrapes`` (trafilatura).
Default sentiment still works on title + snippet when bodies are not fetched.

Post-collection deduplication via ``src.news.dedup.dedup_by_title`` (title-fingerprint
dedup beyond URL dedup to collapse syndication copies).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote_plus

import feedparser
import requests

from src.config.config import CONFIG
from src.utils.time_compat import to_calendar_date

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
    """Fetch and dedupe news items within an inclusive calendar window ``[window_start, window_end]``."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    def collect(
        self,
        symbol: str,
        company_name: str,
        window_start: datetime,
        window_end: datetime,
        max_articles: int = 80,
    ) -> List[NewsArticle]:
        seen_urls: Set[str] = set()
        out: List[NewsArticle] = []

        out.extend(
            self._yahoo_news(symbol, window_start, window_end, seen_urls, max_articles)
        )
        time.sleep(0.4)
        out.extend(
            self._google_rss(
                symbol, company_name, window_start, window_end, seen_urls, max_articles
            )
        )
        time.sleep(0.35)
        out.extend(
            self._bing_rss(symbol, company_name, window_start, window_end, seen_urls, max_articles)
        )
        time.sleep(0.35)
        out.extend(
            self._duckduckgo_lite_html(
                symbol, company_name, window_start, window_end, seen_urls, max(5, max_articles // 4)
            )
        )
        time.sleep(0.35)
        out.extend(
            self.html_discovery_articles(
                symbol,
                company_name,
                seen_urls,
                max_total=min(
                    int(CONFIG.get("NEWS_HTML_DISCOVERY_MAX_TOTAL", 28)),
                    max(10, max_articles),
                ),
            )
        )
        time.sleep(0.3)
        out.extend(
            self._extra_symbol_google_queries(
                symbol, company_name, window_start, window_end, seen_urls, max_articles
            )
        )
        time.sleep(0.3)
        out.extend(
            self._extra_rss_feeds_symbol_scoped(
                symbol, company_name, window_start, window_end, seen_urls, max(8, max_articles // 3)
            )
        )
        time.sleep(0.3)
        out.extend(
            self._india_financial_rss_symbol_scoped(
                symbol, company_name, window_start, window_end, seen_urls, max(10, max_articles // 3)
            )
        )
        time.sleep(0.3)
        try:
            from src.news.newsapi_fetcher import fetch_newsapi_everything

            out.extend(
                fetch_newsapi_everything(
                    symbol,
                    company_name,
                    window_start,
                    window_end,
                    seen_urls,
                    max_items=max(15, max_articles // 2),
                    session=self._session,
                    timeout=self.timeout,
                )
            )
        except Exception as e:
            if (CONFIG.get("NEWSAPI_API_KEY") or "").strip():
                logger.warning("NewsAPI integration error: %s", e)

        out = [
            a
            for a in out
            if a.published is None or (window_start <= a.published <= window_end)
        ]
        out.sort(key=lambda a: a.published or datetime.min, reverse=True)
        # Title-fingerprint dedup: collapses syndication copies, keeps highest-credibility source
        try:
            from src.news.dedup import dedup_by_title
            out = dedup_by_title(out)
        except Exception as _dedup_err:
            logger.debug("Title dedup skipped: %s", _dedup_err)
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
        q = f"{company_name} OR {symbol}"
        return self._rss_google_query(q, start, end, seen, cap, source_label="Google News")

    def _rss_google_fetch_url(self, full_q: str, seen: Set[str], cap: int, *, source_label: str) -> List[NewsArticle]:
        url = (
            f"https://news.google.com/rss/search?q={quote_plus(full_q)}"
            f"&hl=en-IN&gl=IN&ceid=IN:en"
        )
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            logger.warning("Google News RSS parse failed (%s): %s", full_q[:80], e)
            return []
        return self._feed_entries_to_articles(parsed, seen, cap, source_label=source_label)

    def _rss_google_query_windowed(
        self,
        q: str,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
        *,
        source_label: str,
    ) -> List[NewsArticle]:
        """
        For wide calendar windows, Google News RSS often returns only a thin **recent** slice unless
        the query includes ``after:YYYY-MM-DD before:YYYY-MM-DD`` chunks (reverse-engineered behaviour).
        """
        if re.search(r"\bafter:\d{4}-\d{2}-\d{2}", q, flags=re.I) or re.search(
            r"\bbefore:\d{4}-\d{2}-\d{2}", q, flags=re.I
        ):
            return self._rss_google_fetch_url(q, seen, cap, source_label=source_label)

        d0 = to_calendar_date(window_start)
        d1 = to_calendar_date(window_end)
        span = (d1 - d0).days + 1
        threshold = int(CONFIG.get("NEWS_GOOGLE_CHUNK_THRESHOLD_DAYS", 90))
        if span <= threshold:
            return self._rss_google_fetch_url(q, seen, cap, source_label=source_label)

        chunk_days = max(30, int(CONFIG.get("NEWS_GOOGLE_CHUNK_DAYS", 120)))
        max_chunks = max(1, int(CONFIG.get("NEWS_GOOGLE_MAX_CHUNKS", 20)))
        chunks: List[Tuple[date, date]] = []
        cur = d0
        while cur <= d1 and len(chunks) < max_chunks:
            end_c = min(cur + timedelta(days=chunk_days - 1), d1)
            chunks.append((cur, end_c))
            cur = end_c + timedelta(days=1)

        per = max(6, cap // max(len(chunks), 1))
        acc: List[NewsArticle] = []
        for i, (a, b) in enumerate(chunks):
            before_excl = b + timedelta(days=1)
            fq = f"{q} after:{a.isoformat()} before:{before_excl.isoformat()}"
            acc.extend(self._rss_google_fetch_url(fq, seen, per, source_label=source_label))
            if i + 1 < len(chunks):
                time.sleep(0.22)
        logger.info(
            "Google News RSS: used %d date chunks for span=%dd (query prefix %.60s…)",
            len(chunks),
            span,
            q,
        )
        return acc

    def _rss_google_query(
        self,
        q: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
        *,
        source_label: str,
    ) -> List[NewsArticle]:
        return self._rss_google_query_windowed(q, start, end, seen, cap, source_label=source_label)

    def _feed_entries_to_articles(
        self,
        parsed: Any,
        seen: Set[str],
        cap: int,
        *,
        source_label: str,
    ) -> List[NewsArticle]:
        items: List[NewsArticle] = []
        for e in getattr(parsed, "entries", []) or []:
            if len(items) >= max(cap * 2, cap + 25):
                break
            link = getattr(e, "link", "") or ""
            if not link or link in seen:
                continue
            title = (getattr(e, "title", "") or "").strip()
            if not title:
                continue
            summary = ""
            if hasattr(e, "summary"):
                summary = self._strip_html(getattr(e, "summary", "") or "")[:800]
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
                    source=source_label,
                    summary=summary,
                )
            )
        return items

    @staticmethod
    def _haystack(a: NewsArticle) -> str:
        return f"{a.title} {a.summary}".lower()

    @staticmethod
    def _matches_symbol_scope(text: str, symbol: str, company_name: str) -> bool:
        sym = symbol.strip().upper()
        blob = text.upper()
        if len(sym) >= 4:
            if sym in blob:
                return True
        else:
            if re.search(rf"\b{re.escape(sym)}\b", text.upper()):
                return True
        low = text.lower()
        for w in company_name.replace(",", " ").replace(".", " ").split():
            w = w.strip().lower()
            if len(w) >= 4 and w in low:
                return True
        return False

    def _extra_symbol_google_queries(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        max_articles: int,
    ) -> List[NewsArticle]:
        queries = [
            f"{symbol} NSE OR {symbol} stock India",
            f'"{company_name}" earnings OR results OR guidance India',
            f"{symbol} OR {company_name} analyst rating OR target India",
            f'({company_name} OR {symbol}) (site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:business-standard.com)',
        ]
        out: List[NewsArticle] = []
        per = max(6, max_articles // max(3, len(queries)))
        for q in queries:
            out.extend(
                self._rss_google_query_windowed(q, start, end, seen, per, source_label="Google News")
            )
            time.sleep(0.28)
        return out

    def _article_from_feed_entry(self, e: Any, source_label: str) -> Optional[NewsArticle]:
        link = getattr(e, "link", "") or ""
        if not link:
            return None
        title = (getattr(e, "title", "") or "").strip()
        if not title:
            return None
        summary = ""
        if hasattr(e, "summary"):
            summary = self._strip_html(getattr(e, "summary", "") or "")[:800]
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
        return NewsArticle(
            title=title,
            url=link,
            published=pub,
            source=source_label,
            summary=summary,
        )

    def _extra_rss_feeds_symbol_scoped(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        feeds = CONFIG.get("NEWS_EXTRA_RSS_FEEDS") or []
        if isinstance(feeds, str):
            feeds = [u.strip() for u in feeds.split(",") if u.strip()]
        if not feeds:
            return []
        out: List[NewsArticle] = []
        for i, url in enumerate(feeds):
            label = f"RSS+ ({url.split('/')[2][:40]})"
            try:
                r = self._session.get(url.strip(), timeout=self.timeout)
                r.raise_for_status()
                parsed = feedparser.parse(r.content)
            except Exception as e:
                logger.warning("RSS fetch failed (%s): %s", url[:80], e)
                continue
            for e in getattr(parsed, "entries", []) or []:
                if len(out) >= cap:
                    break
                art = self._article_from_feed_entry(e, source_label=label)
                if art is None or art.url in seen:
                    continue
                if not self._matches_symbol_scope(self._haystack(art), symbol, company_name):
                    continue
                seen.add(art.url)
                out.append(art)
            if len(out) >= cap:
                break
            time.sleep(0.35)
        return out[:cap]

    def collect_from_extra_rss_market(
        self,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
        *,
        market_keywords: Optional[List[str]] = None,
    ) -> List[NewsArticle]:
        """
        Same configured RSS feeds as symbol path, but keep rows that match **market** keywords
        (Nifty, RBI, crude, etc.) instead of ticker/company.
        """
        feeds = CONFIG.get("NEWS_EXTRA_RSS_FEEDS") or []
        if isinstance(feeds, str):
            feeds = [u.strip() for u in feeds.split(",") if u.strip()]
        kws = market_keywords or [
            "nifty",
            "sensex",
            "nse",
            "bse",
            "india",
            "market",
            "stock",
            "rbi",
            "rupee",
            "crude",
            "oil",
            "fii",
            "dii",
            "gdp",
            "inflation",
            "bond",
            "yield",
        ]
        out: List[NewsArticle] = []
        # Built-in Tier-2 India feeds first
        out.extend(
            self._india_financial_rss_market(
                window_start, window_end, seen, max(8, cap // 2), market_keywords=kws
            )
        )
        for i, url in enumerate(feeds):
            if len(out) >= cap:
                break
            label = f"Market RSS ({url.split('/')[2][:30]})"
            try:
                r = self._session.get(url.strip(), timeout=self.timeout)
                r.raise_for_status()
                parsed = feedparser.parse(r.content)
            except Exception as e:
                logger.warning("Market RSS fetch failed (%s): %s", url[:80], e)
                continue
            for e in getattr(parsed, "entries", []) or []:
                if len(out) >= cap:
                    break
                art = self._article_from_feed_entry(e, source_label=label)
                if art is None or art.url in seen:
                    continue
                hay = self._haystack(art)
                if not any(k in hay for k in kws):
                    continue
                seen.add(art.url)
                out.append(art)
            if len(out) >= cap:
                break
            time.sleep(0.3)
        return out[:cap]

    def _bing_rss_query(
        self,
        q: str,
        _start: datetime,
        _end: datetime,
        seen: Set[str],
        cap: int,
        *,
        source_label: str = "Bing News",
    ) -> List[NewsArticle]:
        """Bing News RSS — best-effort; query string is caller-defined."""
        items: List[NewsArticle] = []
        url = f"https://www.bing.com/news/search?q={quote_plus(q)}&format=rss&cc=IN"
        try:
            r = self._session.get(url, timeout=self.timeout)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
        except Exception as e:
            logger.warning("Bing News RSS failed (%s): %s", q[:60], e)
            return items
        for e in getattr(parsed, "entries", []) or []:
            if len(items) >= max(8, cap):
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
            seen.add(link)
            items.append(
                NewsArticle(
                    title=title,
                    url=link,
                    published=pub,
                    source=source_label,
                    summary=summary,
                )
            )
        return items

    def _bing_rss(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        q = f"{company_name} {symbol} India stock NSE"
        return self._bing_rss_query(q, start, end, seen, max(8, cap // 3), source_label="Bing News")

    def html_discovery_articles(
        self,
        symbol: str,
        company_name: str,
        seen: Set[str],
        *,
        max_total: int,
    ) -> List[NewsArticle]:
        """Bing + DuckDuckGo HTML search pages → extra article URLs (see ``html_discovery``)."""
        if not CONFIG.get("NEWS_HTML_DISCOVERY_ENABLED", True):
            return []
        try:
            from src.news.html_discovery import discover_from_search_pages

            return discover_from_search_pages(
                self._session,
                symbol,
                company_name,
                seen,
                max_total=max(0, int(max_total)),
                timeout=self.timeout,
            )
        except Exception as e:
            logger.warning("HTML discovery skipped: %s", e)
            return []

    def _duckduckgo_lite_html(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        """DuckDuckGo HTML lite results — fragile; capped; date filter applied client-side."""
        items: List[NewsArticle] = []
        q = f"{symbol} {company_name} stock India news"
        url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(q)}"
        try:
            r = self._session.get(url, timeout=self.timeout)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            logger.warning("DuckDuckGo lite fetch failed: %s", e)
            return items
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href*='http']"):
                if len(items) >= cap:
                    break
                href = (a.get("href") or "").strip()
                if not href.startswith("http") or "duckduckgo" in href:
                    continue
                if href in seen:
                    continue
                title = (a.get_text() or "").strip()
                if len(title) < 12:
                    continue
                seen.add(href)
                items.append(
                    NewsArticle(
                        title=title[:500],
                        url=href,
                        published=None,
                        source="DuckDuckGo (web)",
                        summary="",
                    )
                )
        except Exception as e:
            logger.warning("DuckDuckGo lite parse failed: %s", e)
        return items

    def rss_google_query(
        self,
        q: str,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
        *,
        source_label: str = "Google News",
    ) -> List[NewsArticle]:
        """Public wrapper for multi-query callers (e.g. market sentiment). Uses date-chunking when window is wide."""
        return self._rss_google_query_windowed(
            q, window_start, window_end, seen, cap, source_label=source_label
        )

    def bing_news_query(
        self,
        symbol: str,
        company_name: str,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        return self._bing_rss(symbol, company_name, window_start, window_end, seen, cap)

    def bing_news_query_raw(
        self,
        q: str,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
        *,
        source_label: str = "Bing News",
    ) -> List[NewsArticle]:
        """Arbitrary Bing News RSS query (for market-context multi-query)."""
        return self._bing_rss_query(q, window_start, window_end, seen, cap, source_label=source_label)

    def duckduckgo_lite_query(
        self,
        symbol: str,
        company_name: str,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        return self._duckduckgo_lite_html(symbol, company_name, window_start, window_end, seen, cap)

    # Built-in India financial RSS feeds (Tier 2 sources, always polled)
    _INDIA_FINANCIAL_RSS: List[tuple] = [
        ("https://feeds.feedburner.com/ndtvprofit-latest", "NDTV Profit"),
        ("https://www.livemint.com/rss/markets", "Mint"),
        ("https://www.business-standard.com/rss/markets-106.rss", "Business Standard"),
        ("https://www.thehindubusinessline.com/markets/feeder/default.rss", "BusinessLine"),
        ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "Economic Times"),
        ("https://www.moneycontrol.com/rss/results.xml", "MoneyControl"),
        ("https://www.financialexpress.com/market/feed/", "Financial Express"),
    ]

    def _india_financial_rss_symbol_scoped(
        self,
        symbol: str,
        company_name: str,
        start: datetime,
        end: datetime,
        seen: Set[str],
        cap: int,
    ) -> List[NewsArticle]:
        """
        Poll built-in Tier-2 India financial RSS feeds and keep articles
        that match the target symbol/company.  These feeds are always active
        (no config key needed) unlike the user-configurable PEAD_NEWS_EXTRA_RSS_FEEDS.
        """
        out: List[NewsArticle] = []
        for feed_url, label in self._INDIA_FINANCIAL_RSS:
            if len(out) >= cap:
                break
            try:
                r = self._session.get(feed_url.strip(), timeout=self.timeout)
                r.raise_for_status()
                parsed = feedparser.parse(r.content)
            except Exception as e:
                logger.debug("India financial RSS fetch failed (%s): %s", feed_url[:60], e)
                continue
            for e in getattr(parsed, "entries", []) or []:
                if len(out) >= cap:
                    break
                art = self._article_from_feed_entry(e, source_label=label)
                if art is None or art.url in seen:
                    continue
                if not self._matches_symbol_scope(self._haystack(art), symbol, company_name):
                    continue
                seen.add(art.url)
                out.append(art)
            time.sleep(0.25)
        if out:
            logger.info(
                "news_ingest.source source=india_financial_rss symbol=%s fetched=%d",
                symbol,
                len(out),
            )
        return out[:cap]

    def _india_financial_rss_market(
        self,
        window_start: datetime,
        window_end: datetime,
        seen: Set[str],
        cap: int,
        *,
        market_keywords: Optional[List[str]] = None,
    ) -> List[NewsArticle]:
        """
        Same built-in Tier-2 feeds for the market-context pass (keyword-filtered).
        """
        kws = market_keywords or [
            "nifty", "sensex", "nse", "bse", "india", "market", "stock",
            "rbi", "rupee", "crude", "oil", "fii", "dii", "gdp", "inflation",
            "bond", "yield", "budget", "rate",
        ]
        out: List[NewsArticle] = []
        for feed_url, label in self._INDIA_FINANCIAL_RSS:
            if len(out) >= cap:
                break
            try:
                r = self._session.get(feed_url.strip(), timeout=self.timeout)
                r.raise_for_status()
                parsed = feedparser.parse(r.content)
            except Exception as e:
                logger.debug("India financial market RSS failed (%s): %s", feed_url[:60], e)
                continue
            for e in getattr(parsed, "entries", []) or []:
                if len(out) >= cap:
                    break
                art = self._article_from_feed_entry(e, source_label=label)
                if art is None or art.url in seen:
                    continue
                hay = self._haystack(art)
                if not any(k in hay for k in kws):
                    continue
                seen.add(art.url)
                out.append(art)
            time.sleep(0.22)
        return out[:cap]

    @staticmethod
    def _strip_html(s: str) -> str:
        try:
            from bs4 import BeautifulSoup

            return BeautifulSoup(s, "html.parser").get_text(separator=" ", strip=True)
        except Exception:
            return s
