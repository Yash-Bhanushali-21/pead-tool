"""
NSE/BSE corporate announcements fetcher.

Fetches exchange-primary filings for a symbol in a calendar window.
These are SEBI-mandated disclosures: board meetings, financial results,
corporate actions, regulatory notices.

Sources tried in order:
  1. NSE public API  (corp-info announcements endpoint, no auth required)
  2. BSE public API  (announcements endpoint, no auth required)

Each announcement is returned as a NewsArticle with:
  source = "NSE Announcement" | "BSE Announcement"
  published = filing timestamp (UTC)
  summary = subject + description snippet
  scrape_metadata = {"exchange": ..., "filing_type": ..., "attachment": ...}

Controlled by NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED (default True).
Timeout: NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S (default 15).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import requests

from src.config.config import CONFIG
from src.news.collector import NewsArticle

logger = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockResearchTool/1.0; research-only)",
    "Accept": "application/json, text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# NSE public announcement endpoint (no key required; polite use only)
_NSE_ANNOUNCE_URL = (
    "https://www.nseindia.com/api/corp-info-api"
    "?index=equities&symbol={symbol}&section=announcements"
)

# BSE public announcement endpoint
_BSE_ANNOUNCE_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/AnnGetAnnouncementsDetails/w"
    "?strscripcd={bse_code}&Category=Board%20Meeting&Fdate={from_date}&TDate={to_date}"
)

_NSE_CORP_ACTIONS_URL = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&symbol={symbol}"
)


def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_NSE_HEADERS)
    # Establish a cookie jar by hitting the homepage first (NSE requires this)
    try:
        s.get("https://www.nseindia.com/", timeout=8)
        time.sleep(0.5)
    except Exception:
        pass
    return s


def _parse_nse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except ValueError:
            continue
    return None


def _fetch_nse_announcements(
    session: requests.Session,
    symbol: str,
    window_start: datetime,
    window_end: datetime,
    seen: Set[str],
    timeout: int,
) -> List[NewsArticle]:
    url = _NSE_ANNOUNCE_URL.format(symbol=symbol.upper())
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.debug("NSE announcements fetch failed for %s: %s", symbol, e)
        return []

    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("data") or data.get("announcements") or []

    results: List[NewsArticle] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or item.get("desc") or "").strip()
        if not subject:
            continue
        raw_dt = item.get("an_dt") or item.get("date") or item.get("bm_desc")
        pub = _parse_nse_date(str(raw_dt)) if raw_dt else None
        if pub and not (window_start <= pub <= window_end):
            continue
        attch = str(item.get("attchmntFile") or item.get("attachment") or "")
        url_key = f"NSE::{symbol}::{subject}::{str(raw_dt)}"
        if url_key in seen:
            continue
        seen.add(url_key)
        desc = str(item.get("desc") or item.get("details") or "")[:400]
        results.append(
            NewsArticle(
                title=f"[NSE Filing] {subject}",
                url=url_key,
                published=pub,
                source="NSE Announcement",
                summary=desc,
                scrape_metadata={
                    "exchange": "NSE",
                    "filing_type": _classify_nse_subject(subject),
                    "attachment": bool(attch),
                    "raw_date": str(raw_dt),
                },
            )
        )
    logger.info(
        "news_ingest.source source=NSE_Announcement symbol=%s fetched=%d",
        symbol,
        len(results),
    )
    return results


def _fetch_nse_corporate_actions(
    session: requests.Session,
    symbol: str,
    window_start: datetime,
    window_end: datetime,
    seen: Set[str],
    timeout: int,
) -> List[NewsArticle]:
    url = _NSE_CORP_ACTIONS_URL.format(symbol=symbol.upper())
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.debug("NSE corp actions fetch failed for %s: %s", symbol, e)
        return []

    items: list = data if isinstance(data, list) else (data.get("data") or [])
    results: List[NewsArticle] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or item.get("series") or "").strip()
        action_type = str(item.get("faceVal") or item.get("purpose") or "Corporate Action").strip()
        ex_date_raw = item.get("exDate") or item.get("ex_date")
        pub = _parse_nse_date(str(ex_date_raw)) if ex_date_raw else None
        if pub and not (window_start <= pub <= window_end):
            continue
        url_key = f"NSE_CA::{symbol}::{subject}::{str(ex_date_raw)}"
        if url_key in seen:
            continue
        seen.add(url_key)
        results.append(
            NewsArticle(
                title=f"[NSE Corp Action] {action_type} — {symbol}",
                url=url_key,
                published=pub,
                source="NSE Announcement",
                summary=subject,
                scrape_metadata={
                    "exchange": "NSE",
                    "filing_type": "CORPORATE_ACTION",
                    "attachment": False,
                    "raw_date": str(ex_date_raw),
                },
            )
        )
    logger.info(
        "news_ingest.source source=NSE_CorpAction symbol=%s fetched=%d",
        symbol,
        len(results),
    )
    return results


def _classify_nse_subject(subject: str) -> str:
    """Map NSE subject line to event type (mirrors event_classifier taxonomy)."""
    s = subject.lower()
    if any(k in s for k in ("financial results", "quarterly results", "annual results", "results")):
        return "EARNINGS"
    if any(k in s for k in ("dividend", "buyback", "buy back", "bonus", "split", "rights")):
        return "CORPORATE_ACTION"
    if any(k in s for k in ("board meeting", "agm", "egm")):
        return "GUIDANCE"
    if any(k in s for k in ("acquisition", "merger", "amalgamation", "stake")):
        return "M_AND_A"
    if any(k in s for k in ("sebi", "nclt", "court", "penalty", "compliance")):
        return "REGULATORY"
    if any(k in s for k in ("ceo", "cfo", "director", "managing director", "board appoints")):
        return "MANAGEMENT"
    return "GENERAL"


def fetch_exchange_announcements(
    symbol: str,
    window_start: datetime,
    window_end: datetime,
    seen: Optional[Set[str]] = None,
    *,
    exchange: str = "NSE",
    timeout: int = 15,
) -> List[NewsArticle]:
    """
    Public entry point — fetches announcements from NSE (and optionally BSE).

    Returns a list of NewsArticle objects pre-classified by filing type.
    Falls back gracefully: network/parse errors return empty list, never raise.
    """
    if not CONFIG.get("NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED", True):
        return []

    if seen is None:
        seen = set()

    timeout = int(CONFIG.get("NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S", timeout))
    session = _nse_session()
    results: List[NewsArticle] = []

    ex = (exchange or "NSE").upper()
    if ex in ("NSE", "BOTH"):
        results.extend(_fetch_nse_announcements(session, symbol, window_start, window_end, seen, timeout))
        time.sleep(0.4)
        results.extend(_fetch_nse_corporate_actions(session, symbol, window_start, window_end, seen, timeout))

    results.sort(key=lambda a: a.published or datetime.min, reverse=True)
    return results


def build_announcements_summary(announcements: List[NewsArticle]) -> Dict[str, Any]:
    """Compact structured summary of exchange announcements for API/digest consumers."""
    if not announcements:
        return {"count": 0, "items": [], "has_earnings": False, "has_corporate_actions": False}

    items = []
    for a in announcements:
        meta = a.scrape_metadata or {}
        items.append({
            "title": a.title,
            "filing_type": meta.get("filing_type", "GENERAL"),
            "exchange": meta.get("exchange", "NSE"),
            "published": a.published.isoformat() if a.published else None,
            "summary": a.summary[:200] if a.summary else "",
            "has_attachment": meta.get("attachment", False),
        })

    filing_types = {i["filing_type"] for i in items}
    return {
        "count": len(items),
        "items": items,
        "has_earnings": "EARNINGS" in filing_types,
        "has_corporate_actions": "CORPORATE_ACTION" in filing_types,
        "has_regulatory": "REGULATORY" in filing_types,
        "filing_type_counts": {
            ft: sum(1 for i in items if i["filing_type"] == ft) for ft in filing_types
        },
    }
