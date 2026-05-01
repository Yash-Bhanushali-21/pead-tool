"""
Title-fingerprint deduplication for collected news articles.

Beyond URL dedup (already in collector), this detects the same story
published on multiple syndication sites with slightly different headlines
(e.g. "TCS Q3 profit rises 12% - Economic Times" vs
     "TCS Q3 profit rises 12% - MoneyControl").

Strategy:
  1. Normalise title → strip punctuation, lowercase, strip trailing
     "- <source name>" suffixes, collapse whitespace.
  2. Hash the normalised title → exact syndication copies collapse.
  3. Among duplicates keep the article with the highest source weight
     (from source_registry).

Controlled by NEWS_DEDUP_TITLE_ENABLED (default True).
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Dict, List

from src.config.config import CONFIG
from src.news.collector import NewsArticle
from src.news.source_registry import get_source_weight

logger = logging.getLogger(__name__)

# Common trailing suffixes added by aggregators/publishers
_SUFFIX_PATTERN = re.compile(
    r"\s*[-|–—]\s*("
    r"economic times|moneycontrol|business standard|livemint|mint|"
    r"ndtv profit|ndtv|financial express|zee business|cnbc|cnbctv18|"
    r"bloomberg|reuters|pti|ians|the hindu|businessline|"
    r"yahoo finance|yahoo|google news|msn|seeking alpha"
    r")[\s.]*$",
    flags=re.IGNORECASE,
)

_NON_ALPHA = re.compile(r"[^a-z0-9\s]")
_MULTI_WS = re.compile(r"\s+")


def _normalise(title: str) -> str:
    t = title.lower().strip()
    t = _SUFFIX_PATTERN.sub("", t)
    t = _NON_ALPHA.sub(" ", t)
    t = _MULTI_WS.sub(" ", t).strip()
    return t


def _fingerprint(title: str) -> str:
    return hashlib.sha1(_normalise(title).encode()).hexdigest()


def dedup_by_title(articles: List[NewsArticle]) -> List[NewsArticle]:
    """
    Return deduplicated list: for each title fingerprint keep the article
    with the highest source credibility weight.  Articles with unique
    fingerprints pass through unchanged.

    Skipped when NEWS_DEDUP_TITLE_ENABLED=false.
    """
    if not CONFIG.get("NEWS_DEDUP_TITLE_ENABLED", True):
        return articles

    best: Dict[str, NewsArticle] = {}
    best_weight: Dict[str, float] = {}

    for art in articles:
        fp = _fingerprint(art.title)
        w = get_source_weight(art.source)
        if fp not in best or w > best_weight[fp]:
            best[fp] = art
            best_weight[fp] = w

    # Preserve original order using first-seen position
    seen_fps: Dict[str, int] = {}
    for i, art in enumerate(articles):
        fp = _fingerprint(art.title)
        if fp not in seen_fps:
            seen_fps[fp] = i

    result = sorted(best.values(), key=lambda a: seen_fps[_fingerprint(a.title)])
    removed = len(articles) - len(result)
    if removed:
        logger.info("news_dedup title_fingerprint removed=%d kept=%d", removed, len(result))
    return result
