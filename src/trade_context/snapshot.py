"""
Lightweight execution snapshot without a full PEAD run (price + technicals only).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

import pandas as pd

from src.technical import TechnicalAnalyzer
from src.technical.market_benchmark import aligned_market_index_close
from src.trade_context.trade_readiness import compute_trade_context


def build_light_results_for_trade_context(
    symbol: str,
    stock_data: pd.DataFrame,
    *,
    data_manager=None,
) -> Dict[str, Any]:
    """
    Minimal ``results`` for :func:`compute_trade_context` — **no synthetic PEAD/fundamental/news**.

    Trade context pillars that need missing inputs (e.g. alignment, model fit without R²) will
    surface as ``null`` with reasons in :func:`compute_trade_context`.
    """
    end = stock_data.index.max()
    if hasattr(end, "to_pydatetime"):
        end_ts = pd.Timestamp(end)
    else:
        end_ts = pd.Timestamp(end)
    bench, bench_sym = (None, "")
    if data_manager is not None:
        bench, bench_sym = aligned_market_index_close(data_manager, stock_data)
    ta = TechnicalAnalyzer().analyze(
        stock_data,
        end_ts,
        symbol=symbol,
        benchmark_close=bench,
        benchmark_symbol=bench_sym,
    )
    return {"technical_analysis": ta}


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
    results = build_light_results_for_trade_context(sym, df, data_manager=data_manager)
    tc = compute_trade_context(results, df)
    return {
        "success": True,
        "symbol": sym,
        "trade_context": tc,
        "technical_analysis": results["technical_analysis"],
        "note": (
            f"Price-only window ~{lookback_calendar_days}d calendar + technicals. "
            "No fabricated fundamentals/news/PEAD inputs; see trade_context.missing_pillars for gaps."
        ),
    }
