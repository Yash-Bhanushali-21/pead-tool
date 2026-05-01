"""Immutable per-run knobs for the equity research orchestration path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class EquityResearchRunOptions:
    """User-visible switches aligned with Tools defaults where applicable."""

    #: When True and ``output_dir`` is set, writes the fundamentals pillar PNG in the fundamentals stage.
    visualize: bool = True
    output_dir: Optional[str] = None
    run_timestamp: Optional[str] = None
    include_news: bool = True
    news_lookback_days: Optional[int] = None
    news_max_articles: Optional[int] = None
    news_scrape_bodies: bool = True
    news_max_scrape: int = 32
    technical_include_chart: bool = True
    technical_include_ai_verdict: bool = False
    include_desk_insight: bool = True
    include_market_sentiment: bool = True
    market_sentiment_max_articles: int = 40
    #: Final OpenAI ``ai_digest`` pass for symbol-scoped news (testing: turn off to save latency/cost).
    include_symbol_news_ai_digest: bool = True
    #: Same for the broader market-context headline pass.
    include_market_news_ai_digest: bool = True
    #: Run NSE/BSE exchange announcements stage (structured filings, no NLP required).
    include_exchange_announcements: bool = True
    #: If ``None``, run the full ordered equity pipeline. If set, run only these stage ids (order
    #: follows the canonical pipeline); ``fetch_price_window`` is auto-inserted when a selected
    #: stage requires OHLCV in ``ctx.workspace``.
    pipeline_stages: Optional[Tuple[str, ...]] = None
