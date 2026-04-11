"""
Fetch full article HTML and extract main text + metadata (title, author, date, hostname).

Uses ``trafilatura`` for extraction. Many publisher sites block bots, use paywalls, or return
CAPTCHA — failures are recorded per-URL without failing the whole batch.

Respect site terms of service; use for research aggregation only.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import trafilatura

from src.news.collector import NewsArticle

logger = logging.getLogger(__name__)


def _metadata_to_dict(meta_obj: Any) -> Dict[str, Any]:
    if meta_obj is None:
        return {}
    if hasattr(meta_obj, "as_dict"):
        try:
            return {k: v for k, v in meta_obj.as_dict().items() if v is not None}
        except Exception:
            pass
    out: Dict[str, Any] = {}
    for attr in (
        "title",
        "author",
        "hostname",
        "sitename",
        "date",
        "description",
        "categories",
        "tags",
    ):
        v = getattr(meta_obj, attr, None)
        if v is not None:
            out[attr] = v
    return out


def fetch_article_body_and_meta(
    url: str,
    *,
    timeout: int = 25,
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """
    Download URL and extract visible article text + metadata.

    Returns (body_text, metadata_dict, error_or_none).
    """
    try:
        html = trafilatura.fetch_url(url, no_ssl=False, options=None)
        if not html or not str(html).strip():
            return "", {}, "empty_response"

        text = trafilatura.extract(html, url=url)
        text = (text or "").strip()

        meta_obj = trafilatura.extract_metadata(html)
        meta = _metadata_to_dict(meta_obj)
        if text:
            meta["word_count"] = len(text.split())
        return text, meta, None
    except Exception as e:
        logger.debug("scrape failed %s: %s", url[:80], e)
        return "", {}, str(e)


def enrich_articles_with_scrapes(
    articles: List[NewsArticle],
    *,
    max_scrape: int,
    delay_seconds: float = 0.35,
) -> None:
    """
    Mutates articles in place: fills ``body_text``, ``scrape_metadata``, ``scrape_error``.

    Only the first ``max_scrape`` articles are fetched (typically most recent first).
    """
    if max_scrape <= 0:
        return

    for i, a in enumerate(articles):
        if i >= max_scrape:
            break
        body, meta, err = fetch_article_body_and_meta(a.url)
        if err:
            a.scrape_error = err
            a.scrape_metadata = {}
        else:
            a.body_text = body
            a.scrape_metadata = meta
            a.scrape_error = None
        if i < min(max_scrape, len(articles)) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)
