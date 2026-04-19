"""
HTML search-result discovery: extract outbound article URLs from Bing / DuckDuckGo HTML pages.

This is **best-effort** (markup changes, bot blocking, CAPTCHAs). Use polite delays and caps.
Respect publisher and search-engine terms of service; research-only aggregation.

Controlled by ``NEWS_HTML_DISCOVERY_ENABLED`` and ``NEWS_HTML_DISCOVERY_MAX_TOTAL``.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests

from src.config.config import CONFIG
from src.news.collector import NewsArticle

logger = logging.getLogger(__name__)

_SKIP_HOST_SUBSTR = (
    "bing.com",
    "microsoft.com",
    "duckduckgo.com",
    "google.com",
    "gstatic.com",
    "facebook.com",
    "instagram.com",
    "pinterest.com",
    "twitter.com",
    "x.com",
    "linkedin.com/feed",
    "youtube.com",
    "youtu.be",
    "reddit.com",
    "amazon.",
    "wikipedia.org",
    "quora.com",
)


def _skip_url(url: str) -> bool:
    u = url.lower().strip()
    if not u.startswith("http"):
        return True
    if any(s in u for s in _SKIP_HOST_SUBSTR):
        return True
    if u.endswith(".pdf"):
        return True
    return False


def _bing_decode_href(href: str) -> str:
    """Resolve Bing tracking / redirect URLs to a canonical https target when possible."""
    if not href:
        return ""
    h = href.strip()
    if h.startswith("/ck/a"):
        h = "https://www.bing.com" + h
    if "bing.com/ck/a" in h:
        try:
            qs = parse_qs(urlparse(h).query)
            u = (qs.get("u") or [None])[0]
            if u:
                return unquote(u)
        except Exception:
            pass
    return h


def _parse_bing_html(html: str, max_items: int) -> List[Tuple[str, str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str]] = []
    for li in soup.select("li.b_algo"):
        if len(out) >= max_items:
            break
        a = li.select_one("h2 a")
        if a is None:
            a = li.select_one("a[href^='http']")
        if a is None:
            continue
        raw = (a.get("href") or "").strip()
        href = _bing_decode_href(raw)
        title = (a.get_text() or "").strip()
        if not href or len(title) < 8:
            continue
        if _skip_url(href):
            continue
        out.append((href, title[:500]))
    return out


def _parse_ddg_html(html: str, max_items: int) -> List[Tuple[str, str]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str]] = []
    for a in soup.select("a.result__a"):
        if len(out) >= max_items:
            break
        href = (a.get("href") or "").strip()
        title = (a.get_text() or "").strip()
        if not href.startswith("http") or len(title) < 8:
            continue
        if _skip_url(href):
            continue
        out.append((href, title[:500]))
    return out


def discover_from_search_pages(
    session: requests.Session,
    symbol: str,
    company_name: str,
    seen: Set[str],
    *,
    max_total: int,
    timeout: int,
    per_query_cap: int = 12,
    delay_seconds: float = 0.55,
) -> List[NewsArticle]:
    """
    Run a small set of HTML searches and turn result rows into ``NewsArticle`` stubs
    (``published`` often unknown — caller date-filters).
    """
    if not CONFIG.get("NEWS_HTML_DISCOVERY_ENABLED", True):
        return []

    sym = symbol.strip().upper()
    name = (company_name or sym).strip()
    queries = [
        f"{sym} {name} NSE India stock news",
        f'"{name}" OR {sym} India equity news',
        f"{sym} site:livemint.com OR site:business-standard.com OR site:moneycontrol.com",
    ]

    pairs: List[Tuple[str, str]] = []
    for q in queries:
        if len(pairs) >= max_total:
            break
        # Bing web
        try:
            burl = f"https://www.bing.com/search?q={quote_plus(q)}&cc=IN&setlang=en"
            r = session.get(burl, timeout=timeout)
            r.raise_for_status()
            pairs.extend(_parse_bing_html(r.text, per_query_cap))
        except Exception as e:
            logger.debug("Bing HTML discovery failed for %s: %s", q[:60], e)
        time.sleep(delay_seconds)

        if len(pairs) >= max_total:
            break
        # DuckDuckGo HTML (non-lite)
        try:
            durl = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
            r2 = session.get(durl, timeout=timeout)
            r2.raise_for_status()
            pairs.extend(_parse_ddg_html(r2.text, per_query_cap))
        except Exception as e:
            logger.debug("DDG HTML discovery failed for %s: %s", q[:60], e)
        time.sleep(delay_seconds)

    out: List[NewsArticle] = []
    for href, title in pairs:
        if len(out) >= max_total:
            break
        if href in seen:
            continue
        seen.add(href)
        out.append(
            NewsArticle(
                title=title,
                url=href,
                published=None,
                source="HTML search discovery",
                summary="",
            )
        )
    logger.info("HTML search discovery: added %d new URLs for %s", len(out), sym)
    return out
