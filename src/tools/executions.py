"""
Synchronous tool bodies shared by FastAPI /api/tools routes and the PydanticAI chat agent.

Keep behaviour aligned with ``server/tools_routes.py`` handlers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import pandas as pd

from src.agent.announcements import get_latest_announcement_date
from src.analysis.pead_analyzer import PEADAnalyzer
from src.technical.ai_verdict import generate_technical_verdict


def resolve_earnings_date(
    symbol: str,
    announcement_date: Optional[str],
    analyzer: PEADAnalyzer,
) -> pd.Timestamp:
    sym = symbol.strip().upper()
    if announcement_date:
        return pd.to_datetime(announcement_date)
    dt = get_latest_announcement_date(sym, analyzer.data_manager)
    if dt is None:
        raise ValueError(
            "Could not auto-detect announcement date; provide announcement_date (YYYY-MM-DD)."
        )
    return pd.Timestamp(dt)


def execute_fundamentals(analyzer: PEADAnalyzer, symbol: str) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    bundle = analyzer.data_manager.get_company_fundamentals(sym)
    return analyzer.fundamental_analyzer.analyze(sym, bundle)


def execute_technical(
    analyzer: PEADAnalyzer,
    *,
    symbol: str,
    price_window: Literal["pead_event", "explicit_range"] = "pead_event",
    announcement_resolution: Literal["auto", "manual"] = "auto",
    announcement_date: Optional[str] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    include_chart: bool = True,
    include_ai_verdict: bool = False,
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    out_base: Dict[str, Any] = {"symbol": sym, "price_window": price_window}
    stock_data: Optional[pd.DataFrame] = None

    if price_window == "explicit_range":
        if not range_start or not range_end:
            return {
                "success": False,
                "error": "range_start and range_end (YYYY-MM-DD) are required for explicit_range.",
                **out_base,
            }
        start_dt = pd.to_datetime(range_start).to_pydatetime()
        end_dt = pd.to_datetime(range_end).to_pydatetime()
        if start_dt > end_dt:
            return {
                "success": False,
                "error": "range_start must be on or before range_end.",
                **out_base,
                "range_start": range_start,
                "range_end": range_end,
            }
        stock_data = analyzer.data_manager.get_stock_data(sym, start_dt, end_dt)
        out_base["range_start"] = range_start
        out_base["range_end"] = range_end
    else:
        out_base["announcement_resolution"] = announcement_resolution
        if announcement_resolution == "manual":
            if not announcement_date or not str(announcement_date).strip():
                return {
                    "success": False,
                    "error": "announcement_date is required when announcement_resolution is manual.",
                    **out_base,
                }
            ann = pd.to_datetime(announcement_date)
        else:
            try:
                ann = resolve_earnings_date(sym, None, analyzer)
            except ValueError as e:
                return {"success": False, "error": str(e), **out_base}
        ann_dt = ann.to_pydatetime()
        stock_data = analyzer.data_manager.get_stock_data_for_event_window(sym, ann_dt)
        out_base["announcement_date_used"] = str(ann.date())

    if stock_data is None or stock_data.empty:
        err = (
            f"No OHLCV for {sym} in the requested window from NSE/Yahoo. "
            "Widen the explicit range or verify the symbol / announcement date."
        )
        if price_window == "pead_event":
            err += f" (PEAD window around {out_base.get('announcement_date_used', '?')})"
        return {"success": False, "error": err, **out_base}

    idx = stock_data.index
    anchor = pd.Timestamp(idx[-1])
    ta = analyzer.technical_analyzer.analyze(
        stock_data,
        anchor,
        symbol=sym,
        include_chart_payload=include_chart,
    )
    out: Dict[str, Any] = {
        "success": True,
        **out_base,
        "ohlc_index_start": str(idx.min())[:10],
        "ohlc_index_end": str(idx.max())[:10],
        "technical_analysis": ta,
    }
    if include_ai_verdict:
        out["research_verdict"] = generate_technical_verdict(out)
    return out


def execute_scoring_only(
    analyzer: PEADAnalyzer,
    symbol: str,
    announcement_date: Optional[str] = None,
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    try:
        ann = resolve_earnings_date(sym, announcement_date, analyzer)
    except ValueError as e:
        return {"success": False, "error": str(e), "symbol": sym}
    return analyzer.analyze_scoring_only(sym, ann.to_pydatetime())


def execute_trade_readiness_isolated(
    analyzer: PEADAnalyzer,
    symbol: str,
    lookback_days: int = 200,
) -> Dict[str, Any]:
    from src.trade_context.snapshot import fetch_light_trade_context

    sym = symbol.strip().upper()
    full = fetch_light_trade_context(
        sym,
        analyzer.data_manager,
        lookback_calendar_days=int(lookback_days),
    )
    if not full.get("success"):
        return full
    return {
        "success": True,
        "symbol": sym,
        "trade_context": full.get("trade_context"),
        "note": full.get("note"),
    }


def execute_execution_snapshot(
    analyzer: PEADAnalyzer,
    symbol: str,
    lookback_days: int = 200,
) -> Dict[str, Any]:
    from src.trade_context.snapshot import fetch_light_trade_context

    sym = symbol.strip().upper()
    return fetch_light_trade_context(
        sym,
        analyzer.data_manager,
        lookback_calendar_days=int(lookback_days),
    )


def execute_document_pdf(
    analyzer: PEADAnalyzer,
    symbol: str,
    announcement_date: str,
) -> Dict[str, Any]:
    sym = symbol.strip().upper()
    ann = pd.to_datetime(announcement_date)
    p = analyzer.pdf_downloader.get_pdf_path(sym, ann.to_pydatetime())
    if not p or not p.exists():
        return {
            "success": False,
            "error": (
                f"No PDF found for {sym} on {announcement_date}. "
                "Expected filename like {SYMBOL}_{YYYYMMDD}.pdf under the PDF download directory."
            ),
            "symbol": sym,
        }
    parsed = analyzer.pdf_parser.parse_announcement(p)
    text = parsed.get("text") or ""
    return {
        "success": True,
        "path": str(p),
        "text_chars": len(text),
        "text_preview": text[:8000],
        "metrics": parsed.get("metrics"),
        "guidance": parsed.get("guidance"),
        "sentiment": parsed.get("sentiment"),
    }


def execute_yahoo_calendar(symbol: str) -> Dict[str, Any]:
    import yfinance as yf

    sym = symbol.strip().upper()
    t = yf.Ticker(f"{sym}.NS")
    out: Dict[str, Any] = {"symbol": sym, "yahoo_ticker": f"{sym}.NS"}
    cal = getattr(t, "calendar", None)
    if cal is not None and hasattr(cal, "empty") and not cal.empty:
        out["calendar"] = cal.to_dict() if hasattr(cal, "to_dict") else str(cal)
    ed = getattr(t, "earnings_dates", None)
    if ed is not None and hasattr(ed, "empty") and not ed.empty:
        out["earnings_dates_head"] = ed.head(12).to_string()
    return out


def execute_recent_announcements(
    analyzer: PEADAnalyzer,
    top_n: int,
    *,
    visualize: bool = False,
    output_dir: str,
    include_news: bool = True,
    news_lookback_days: Optional[int] = None,
    news_max_articles: Optional[int] = None,
) -> Dict[str, Any]:
    import numpy as np

    from pathlib import Path

    out_base = Path(output_dir).expanduser().resolve()
    out_base.mkdir(parents=True, exist_ok=True)

    df, batch_root = analyzer.analyze_recent_announcements(
        n=int(top_n),
        visualize=visualize,
        output_dir=str(out_base),
        include_news=include_news,
        news_lookback_days=news_lookback_days,
        news_max_articles=news_max_articles,
    )

    if df is None or df.empty:
        return {
            "mode": "recent",
            "success": False,
            "error": "No successful runs or no announcements from NSE feed.",
            "rows": [],
            "batch_root": str(batch_root) if batch_root else None,
        }

    df = df.replace({np.nan: None})
    rows: List[dict[str, Any]] = df.to_dict(orient="records")
    return {
        "mode": "recent",
        "success": True,
        "error": None,
        "top_n": top_n,
        "row_count": len(rows),
        "batch_root": str(batch_root) if batch_root else None,
        "rows": rows,
    }
