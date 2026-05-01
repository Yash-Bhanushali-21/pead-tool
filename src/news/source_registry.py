"""
Source credibility registry for Indian equity news.

Each source entry carries a credibility weight (0.0–1.0) used to compute
weighted-average sentiment scores.  Tier assignments:

  Tier 1 (0.90–1.0)  — Exchange-primary / major international wires
  Tier 2 (0.70–0.89) — Established Indian financial press
  Tier 3 (0.40–0.69) — General aggregators / search-sourced RSS
  Tier 4 (0.10–0.39) — HTML discovery, undated, unknown domains

Weights are config-overridable via NEWS_SOURCE_WEIGHTS (JSON env var).
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from src.config.config import CONFIG

logger = logging.getLogger(__name__)

# ── Default registry ───────────────────────────────────────────────────────────
_DEFAULT_WEIGHTS: Dict[str, float] = {
    # Tier 1 — Exchange / primary wires
    "NSE Announcement": 1.00,
    "BSE Announcement": 1.00,
    "Reuters": 0.95,
    "PTI": 0.93,
    "Bloomberg": 0.95,
    "IANS": 0.88,
    # Tier 2 — Established Indian financial press
    "Business Standard": 0.87,
    "Mint": 0.86,
    "LiveMint": 0.86,
    "NDTV Profit": 0.84,
    "NDTV": 0.80,
    "The Hindu BusinessLine": 0.85,
    "BusinessLine": 0.85,
    "Financial Express": 0.83,
    "Economic Times": 0.82,
    "moneycontrol": 0.80,
    "MoneyControl": 0.80,
    "Zee Business": 0.76,
    "CNBC-TV18": 0.78,
    "CNBCTV18": 0.78,
    "ET Now": 0.77,
    # Tier 3 — Aggregators / search-sourced
    "Yahoo": 0.60,
    "Google News": 0.50,
    "Market (Google)": 0.48,
    "Bing News": 0.45,
    "Market (Bing)": 0.43,
    "DuckDuckGo (web)": 0.38,
    # Tier 4 — Discovery / unknown
    "HTML search discovery": 0.20,
}

# Defaults for tier labels (used in coverage_meta)
_TIER_THRESHOLDS = [
    (0.89, "tier1"),
    (0.69, "tier2"),
    (0.39, "tier3"),
    (0.00, "tier4"),
]

_registry: Optional[Dict[str, float]] = None


def _load_registry() -> Dict[str, float]:
    global _registry
    if _registry is not None:
        return _registry
    base = dict(_DEFAULT_WEIGHTS)
    raw = CONFIG.get("NEWS_SOURCE_WEIGHTS")
    if raw:
        try:
            overrides = json.loads(str(raw))
            if isinstance(overrides, dict):
                for k, v in overrides.items():
                    try:
                        base[str(k)] = float(v)
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logger.warning("NEWS_SOURCE_WEIGHTS parse error: %s", e)
    _registry = base
    return _registry


def get_source_weight(source_label: str) -> float:
    """Return credibility weight for a source label; defaults to 0.40 (Tier 3)."""
    reg = _load_registry()
    if source_label in reg:
        return reg[source_label]
    sl = source_label.lower()
    for key, val in reg.items():
        if key.lower() in sl or sl in key.lower():
            return val
    # RSS+ dynamic labels contain the domain name
    if sl.startswith("rss+") or sl.startswith("market rss"):
        return 0.55
    return 0.40


def get_source_tier(weight: float) -> str:
    for threshold, label in _TIER_THRESHOLDS:
        if weight >= threshold:
            return label
    return "tier4"


def invalidate_cache() -> None:
    """Force reload of registry (useful in tests)."""
    global _registry
    _registry = None
