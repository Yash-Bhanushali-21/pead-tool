"""
Lightweight execution snapshot without a full PEAD run (price + technicals only).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd

from src.technical import TechnicalAnalyzer
from src.trade_context.trade_readiness import compute_trade_context


def build_light_results_for_trade_context(
    symbol: str,
    stock_data: pd.DataFrame,
) -> Dict[str, Any]:
    """Minimal ``results`` shape for :func:`compute_trade_context`."""
    end = stock_data.index.max()
    if hasattr(end, "to_pydatetime"):
        end_ts = pd.Timestamp(end)
    else:
        end_ts = pd.Timestamp(end)
    ta = TechnicalAnalyzer().analyze(stock_data, end_ts, symbol=symbol)
    return {
        "composite_score": {"rating": "HOLD", "data_quality": {}},
        "fundamental_analysis": {"stance": "not run — use full PEAD for fundamentals"},
        "technical_analysis": ta,
        "news_sentiment": None,
        "market_model": {"beta": None, "r_squared": None},
    }


def fetch_light_trade_context(
    symbol: str,
    data_manager,
    lookback_calendar_days: int = 200,
) -> Dict[str, Any]:
    """
    Pull recent OHLCV and compute trade-context pillars without PEAD/CAR/news.

    For a full cross-check, run ``analyze_announcement`` instead.
    """
    sym = symbol.strip().upper()
    end = datetime.now()
    start = end - timedelta(days=lookback_calendar_days)
    df = data_manager.get_stock_data(sym, start, end)
    if df is None or df.empty:
        return {
            "success": False,
            "error": "Insufficient price history for execution snapshot",
            "symbol": sym,
        }
    results = build_light_results_for_trade_context(sym, df)
    tc = compute_trade_context(results, df)
    return {
        "success": True,
        "symbol": sym,
        "trade_context": tc,
        "technical_analysis": results["technical_analysis"],
        "note": f"Fundamentals/news/PEAD omitted — price window ~{lookback_calendar_days}d. "
        "Use run_full_pead_pipeline for unified desk view.",
    }
