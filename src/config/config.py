"""
Single source of truth: ``CONFIG`` dict populated from environment (``.env`` + process env).

Import ``CONFIG`` for explicit dict access, or ``config`` (attribute-style view) for legacy code.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _get(key: str, default: Any = None) -> Any:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v


def _int(key: str, default: int) -> int:
    raw = _get(key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    raw = _get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _float(key: str, default: float) -> float:
    raw = _get(key)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


def _csv_url_list(key: str, default_csv: str) -> List[str]:
    """Comma-separated URLs (e.g. RSS) from env; trims empties."""
    raw = _get(key, default_csv)
    if not raw:
        return []
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _int_list(key: str, default: List[int]) -> List[int]:
    raw = _get(key)
    if not raw:
        return list(default)
    out: List[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out if out else list(default)


def _build_scoring_weights() -> Dict[str, float]:
    """Allow optional env overrides like SCORING_EARNINGS_SURPRISE=0.25"""
    base = {
        "earnings_surprise": 0.25,
        "price_reaction": 0.20,
        "drift_confirmation": 0.25,
        "earnings_quality": 0.15,
        "contextual": 0.15,
    }
    env_map = {
        "earnings_surprise": "SCORING_EARNINGS_SURPRISE",
        "price_reaction": "SCORING_PRICE_REACTION",
        "drift_confirmation": "SCORING_DRIFT_CONFIRMATION",
        "earnings_quality": "SCORING_EARNINGS_QUALITY",
        "contextual": "SCORING_CONTEXTUAL",
    }
    for k, env_k in env_map.items():
        v = _get(env_k)
        if v is not None:
            try:
                base[k] = float(str(v).strip())
            except ValueError:
                pass
    return base


def _positive_keywords() -> List[str]:
    return [
        "beat",
        "exceed",
        "strong",
        "growth",
        "robust",
        "positive",
        "expansion",
        "improvement",
        "record",
        "highest",
        "outperform",
    ]


def _negative_keywords() -> List[str]:
    return [
        "miss",
        "weak",
        "decline",
        "loss",
        "concern",
        "challenge",
        "deteriorate",
        "poor",
        "lower",
        "negative",
        "underperform",
    ]


CONFIG: Dict[str, Any] = {
    # —— Secrets & API (from .env) ——
    "OPENAI_API_KEY": _get("OPENAI_API_KEY", "") or "",
    "PEAD_CORS_ORIGINS": _get(
        "PEAD_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ),
    # —— OpenAI model names ——
    "OPENAI_NEWS_MODEL": _get("OPENAI_NEWS_MODEL", "gpt-4o-mini"),
    "OPENAI_TECH_VERDICT_MODEL": _get("OPENAI_TECH_VERDICT_MODEL", "gpt-4o-mini"),
    "OPENAI_EQUITY_DESK_MODEL": _get("OPENAI_EQUITY_DESK_MODEL", "gpt-4o-mini"),
    "AGENT_MODEL": _get("AGENT_MODEL", "openai:gpt-4o-mini"),
    "AGENT_SYNTHESIS_MODEL": _get("AGENT_SYNTHESIS_MODEL", "openai:gpt-4o-mini"),
    # —— Market / PEAD ——
    "ESTIMATION_WINDOW": _int("ESTIMATION_WINDOW", 120),
    "MARKET_INDEX": _get("MARKET_INDEX", "^NSEI"),
    "CAR_WINDOWS": _int_list("CAR_WINDOWS", [1, 10, 30, 60, 90]),
    "SIGNIFICANCE_LEVEL": _float("SIGNIFICANCE_LEVEL", 0.05),
    "TOP_N_COMPANIES": _int("TOP_N_COMPANIES", 10),
    "MIN_TRADING_DAYS": _int("MIN_TRADING_DAYS", 80),
    "PDF_DOWNLOAD_DIR": _get("PDF_DOWNLOAD_DIR", "./data/announcements"),
    "CACHE_DIR": _get("CACHE_DIR", "./data/cache"),
    "VOLUME_SPIKE_THRESHOLD": _float("VOLUME_SPIKE_THRESHOLD", 2.0),
    "VOLUME_LOOKBACK": _int("VOLUME_LOOKBACK", 20),
    "CFO_QUALITY_THRESHOLD": _float("CFO_QUALITY_THRESHOLD", 1.0),
    "MARGIN_EXPANSION_THRESHOLD": _float("MARGIN_EXPANSION_THRESHOLD", 0.02),
    "DRIFT_SHORT_WINDOW": _int("DRIFT_SHORT_WINDOW", 5),
    "DRIFT_MEDIUM_WINDOW": _int("DRIFT_MEDIUM_WINDOW", 10),
    "DRIFT_LONG_WINDOW": _int("DRIFT_LONG_WINDOW", 30),
    "NEWS_LOOKBACK_DAYS": _int("NEWS_LOOKBACK_DAYS", 90),
    "NEWS_MAX_ARTICLES": _int("NEWS_MAX_ARTICLES", 80),
    # Extra RSS URLs for news/market collectors (comma-separated). Defaults: India business wires.
    "NEWS_EXTRA_RSS_FEEDS": _csv_url_list(
        "PEAD_NEWS_EXTRA_RSS_FEEDS",
        "https://www.moneycontrol.com/rss/latestnews.xml,"
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    ),
    # Final LLM digest on top of lexicon + synthesis (requires OPENAI_API_KEY).
    "OPENAI_NEWS_DIGEST_MODEL": _get("OPENAI_NEWS_DIGEST_MODEL", "") or None,
    "NEWS_AI_DIGEST_ENABLED": _bool("NEWS_AI_DIGEST_ENABLED", True),
    # Google News RSS: slice long windows with after:/before: (unofficial but widely used).
    "NEWS_GOOGLE_CHUNK_THRESHOLD_DAYS": _int("NEWS_GOOGLE_CHUNK_THRESHOLD_DAYS", 90),
    "NEWS_GOOGLE_CHUNK_DAYS": _int("NEWS_GOOGLE_CHUNK_DAYS", 120),
    "NEWS_GOOGLE_MAX_CHUNKS": _int("NEWS_GOOGLE_MAX_CHUNKS", 20),
    # NewsAPI.org ``/v2/everything`` (optional; set ``NEWSAPI_API_KEY``).
    "NEWSAPI_API_KEY": _get("NEWSAPI_API_KEY", "") or "",
    "NEWSAPI_MAX_RESULTS": _int("NEWSAPI_MAX_RESULTS", 80),
    # HTML search-result link discovery (Bing + DDG HTML; no headless browser).
    "NEWS_HTML_DISCOVERY_ENABLED": _bool("NEWS_HTML_DISCOVERY_ENABLED", True),
    "NEWS_HTML_DISCOVERY_MAX_TOTAL": _int("NEWS_HTML_DISCOVERY_MAX_TOTAL", 28),
    # Trafilatura body fetch cap default for equity pipeline (individual API calls may pass lower).
    "NEWS_BODY_SCRAPE_DEFAULT": _int("NEWS_BODY_SCRAPE_DEFAULT", 32),
    # ── News intelligence enhancements (Issue #2) ──────────────────────────────
    # Title-fingerprint dedup (collapses syndication copies of same story)
    "NEWS_DEDUP_TITLE_ENABLED": _bool("NEWS_DEDUP_TITLE_ENABLED", True),
    # NSE/BSE exchange announcements fetcher (structured filings, no NLP required)
    "NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED": _bool("NEWS_EXCHANGE_ANNOUNCEMENTS_ENABLED", True),
    "NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S": _int("NEWS_EXCHANGE_ANNOUNCEMENTS_TIMEOUT_S", 15),
    # Source credibility weight overrides (JSON dict of {"Source Label": weight})
    "NEWS_SOURCE_WEIGHTS": _get("NEWS_SOURCE_WEIGHTS", "") or None,
    "AGENT_OUTPUT_SUBDIR": _get("AGENT_OUTPUT_SUBDIR", "agent_runs"),
    # Chat persistence (SQLite)
    "CHAT_SQLITE_PATH": _get("CHAT_SQLITE_PATH", "./data/pead_chat.sqlite3"),
    # News citations (defaults to same file as chat if unset)
    "NEWS_SQLITE_PATH": _get("NEWS_SQLITE_PATH", "") or None,
    "CHAT_PERSIST_ENABLED": _bool("CHAT_PERSIST_ENABLED", True),
    # Mem0 (https://github.com/mem0ai/mem0) — optional chat long-term memory; requires ``pip install mem0ai``
    "MEM0_ENABLED": _bool("MEM0_ENABLED", False),
    "MEM0_TOP_K": _int("MEM0_TOP_K", 5),
    "MEM0_DEFAULT_USER_ID": _get("MEM0_DEFAULT_USER_ID", "local"),
    "SCORING_WEIGHTS": _build_scoring_weights(),
    "SENTIMENT_KEYWORDS_POSITIVE": _positive_keywords(),
    "SENTIMENT_KEYWORDS_NEGATIVE": _negative_keywords(),
}


def _ensure_directories() -> None:
    os.makedirs(CONFIG["PDF_DOWNLOAD_DIR"], exist_ok=True)
    os.makedirs(CONFIG["CACHE_DIR"], exist_ok=True)
    os.makedirs(
        os.path.join("./output", str(CONFIG["AGENT_OUTPUT_SUBDIR"])),
        exist_ok=True,
    )
    _p = Path(CONFIG["CHAT_SQLITE_PATH"]).expanduser().resolve()
    _p.parent.mkdir(parents=True, exist_ok=True)


_ensure_directories()


class ConfigView:
    """Read-only attribute access over ``CONFIG`` (``config.AGENT_MODEL``)."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return CONFIG[name]
        except KeyError:
            raise AttributeError(name) from None


config = ConfigView()

__all__ = ["CONFIG", "config", "ConfigView", "_REPO_ROOT"]
