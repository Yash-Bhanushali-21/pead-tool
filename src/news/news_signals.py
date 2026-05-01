"""
Quantitative news signals derived from classified + scored articles.

Three signals are computed and returned in the ``news_signals`` key of the
sentiment pipeline output:

  news_velocity        — articles/day in window vs baseline; labels: low/normal/elevated/spike
  source_agreement     — 0–1 score; high = credible sources align; low = conflicting coverage
  event_tone           — weighted sentiment over EARNINGS + GUIDANCE articles only (0–100 scale)
                         null when no earnings/guidance articles are present

All inputs use the per-article (article, polarity, event_type, source_weight) quadruples
produced by the enhanced sentiment pipeline.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _velocity_label(velocity: float) -> str:
    if velocity < 0.5:
        return "low"
    if velocity < 2.0:
        return "normal"
    if velocity < 6.0:
        return "elevated"
    return "spike"


def compute_news_velocity(
    article_dates: List[Optional[datetime]],
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, Any]:
    """
    Articles-per-day in the window.  Undated articles contribute to count
    but not to the date distribution.
    """
    span_days = max(1.0, (window_end - window_start).total_seconds() / 86400)
    total = len(article_dates)
    velocity = total / span_days
    label = _velocity_label(velocity)
    return {
        "articles_per_day": round(velocity, 3),
        "total_articles": total,
        "window_days": round(span_days, 1),
        "velocity_label": label,
    }


def compute_source_agreement(
    polarities: List[float],
    weights: List[float],
    min_tier2_articles: int = 2,
) -> Dict[str, Any]:
    """
    Agreement score: 1 − normalised weighted standard deviation of polarities.

    A score near 1.0 means credible sources agree on direction.
    A score near 0.0 means credible sources are split.

    Only articles with weight >= 0.70 (Tier 2+) contribute to agreement;
    if fewer than ``min_tier2_articles`` qualify, returns null (insufficient coverage).
    """
    pairs: List[Tuple[float, float]] = [
        (p, w) for p, w in zip(polarities, weights) if w >= 0.70
    ]
    if len(pairs) < min_tier2_articles:
        return {
            "source_agreement_score": None,
            "source_agreement_label": "insufficient_tier2_coverage",
            "tier2_articles_used": len(pairs),
        }

    total_w = sum(w for _, w in pairs)
    wmean = sum(p * w for p, w in pairs) / total_w
    variance = sum(w * (p - wmean) ** 2 for p, w in pairs) / total_w
    std = math.sqrt(variance)
    # Polarity range is [-1, 1] → max std ≈ 1.0; normalise to [0, 1]
    agreement = max(0.0, min(1.0, 1.0 - std))
    label = (
        "high" if agreement >= 0.75
        else "moderate" if agreement >= 0.50
        else "low"
    )
    return {
        "source_agreement_score": round(agreement, 4),
        "source_agreement_label": label,
        "tier2_articles_used": len(pairs),
    }


def compute_event_tone(
    event_types: List[str],
    polarities: List[float],
    weights: List[float],
    target_events: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Source-weighted sentiment score (0–100) restricted to earnings/guidance events.

    ``target_events`` defaults to EARNINGS + GUIDANCE; callers can override.
    """
    if target_events is None:
        target_events = ["EARNINGS", "GUIDANCE"]

    target_set = set(target_events)
    relevant = [
        (p, w)
        for et, p, w in zip(event_types, polarities, weights)
        if et in target_set
    ]

    if not relevant:
        return {
            "event_tone_score": None,
            "event_tone_stance": None,
            "event_tone_article_count": 0,
            "event_tone_target_events": target_events,
        }

    total_w = sum(w for _, w in relevant)
    wmean = sum(p * w for p, w in relevant) / total_w
    score = float(max(0.0, min(100.0, (wmean + 1.0) * 50.0)))
    stance = "bullish" if score >= 58.0 else ("bearish" if score <= 42.0 else "neutral")
    return {
        "event_tone_score": round(score, 2),
        "event_tone_stance": stance,
        "event_tone_article_count": len(relevant),
        "event_tone_target_events": target_events,
    }


def compute_all_signals(
    articles_data: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, Any]:
    """
    Top-level signal computation from the per-article enriched list.

    Each item in ``articles_data`` must have:
      - published: Optional[datetime]
      - polarity: float
      - source_weight: float
      - event_type: str
    """
    dates = [a.get("published") for a in articles_data]
    polarities = [float(a.get("polarity") or 0.0) for a in articles_data]
    weights = [float(a.get("source_weight") or 0.40) for a in articles_data]
    event_types = [str(a.get("event_type") or "GENERAL") for a in articles_data]

    velocity = compute_news_velocity(dates, window_start, window_end)
    agreement = compute_source_agreement(polarities, weights)
    tone = compute_event_tone(event_types, polarities, weights)

    return {
        "news_velocity": velocity,
        "source_agreement": agreement,
        "event_tone": tone,
    }
