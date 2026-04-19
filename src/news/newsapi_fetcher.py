"""
Optional `NewsAPI.org <https://newsapi.org/>`_ ``/v2/everything`` aggregation (developer / paid tiers).

Set ``NEWSAPI_API_KEY`` in the environment. Terms and rate limits are set by NewsAPI; this module
does not bypass them.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import requests

from src.config.config import CONFIG
from src.news.collector import NewsArticle
from src.utils.time_compat import to_calendar_date

logger = logging.getLogger(__name__)

NEWSAPI_EVERYTHING = "https://newsapi.org/v2/everything"


def fetch_newsapi_everything(
    symbol: str,
    company_name: str,
    window_start: datetime,
    window_end: datetime,
    seen: Set[str],
    *,
    max_items: int,
    session: requests.Session,
    timeout: int,
) -> List[NewsArticle]:
    key = (CONFIG.get("NEWSAPI_API_KEY") or "").strip()
    if not key:
        return []

    sym = symbol.strip().upper()
    name = (company_name or sym).strip().replace('"', " ").strip()
    # NewsAPI ``q`` syntax: https://newsapi.org/docs/endpoints/everything
    q = f"({name} OR {sym} OR {sym}.NS) AND (India OR NSE OR stock OR shares)"

    fd = to_calendar_date(window_start)
    td = to_calendar_date(window_end)
    hard_max = int(CONFIG.get("NEWSAPI_MAX_RESULTS", 80))
    cap = max(1, min(int(max_items), hard_max))

    out: List[NewsArticle] = []
    page = 1
    page_size = min(100, cap)

    while len(out) < cap and page <= 3:
        params: Dict[str, Any] = {
            "q": q,
            "from": fd.isoformat(),
            "to": td.isoformat(),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "page": page,
            "apiKey": key,
        }
        try:
            r = session.get(NEWSAPI_EVERYTHING, params=params, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("NewsAPI everything request failed (page %s): %s", page, e)
            break

        if payload.get("status") != "ok":
            logger.warning("NewsAPI error: %s", payload.get("message") or payload)
            break

        articles = payload.get("articles") or []
        if not articles:
            break

        for row in articles:
            if len(out) >= cap:
                break
            if not isinstance(row, dict):
                continue
            url = (row.get("url") or "").strip()
            if not url or url in seen:
                continue
            title = (row.get("title") or "").strip()
            if not title:
                continue
            desc = (row.get("description") or row.get("content") or "").strip()
            pub_s = row.get("publishedAt")
            pub: Optional[datetime] = None
            if isinstance(pub_s, str) and pub_s:
                try:
                    raw = pub_s.replace("Z", "+00:00") if pub_s.endswith("Z") else pub_s
                    pub = datetime.fromisoformat(raw)
                    if pub.tzinfo is not None:
                        pub = pub.astimezone(timezone.utc).replace(tzinfo=None)
                except Exception:
                    pub = None
            src_raw = row.get("source")
            if isinstance(src_raw, dict):
                src_name = (str(src_raw.get("name") or "").strip() or "NewsAPI")
            elif isinstance(src_raw, str):
                src_name = src_raw.strip() or "NewsAPI"
            else:
                src_name = "NewsAPI"
            seen.add(url)
            out.append(
                NewsArticle(
                    title=title[:500],
                    url=url,
                    published=pub,
                    source=f"NewsAPI ({src_name})",
                    summary=desc[:1200],
                )
            )

        if len(articles) < page_size:
            break
        page += 1
        time.sleep(0.35)

    logger.info("NewsAPI: collected %d articles for %s", len(out), sym)
    return out
