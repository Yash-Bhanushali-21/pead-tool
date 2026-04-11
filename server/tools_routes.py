"""
Direct PEAD runs from the /tools UI — same knobs as the CLI (no LLM required).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agent.announcements import get_latest_announcement_date
from src.agent.serialize import compact_pead_for_llm
from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.settings import config
from src.news.layer import run_news_sentiment_layer
from src.technical.ai_verdict import generate_technical_verdict
from src.trade_context.snapshot import fetch_light_trade_context

ROOT = Path(__file__).resolve().parent.parent

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _json_safe(obj: Any) -> Any:
    """Make nested numpy/pandas payloads JSON-serializable for FastAPI."""
    return json.loads(json.dumps(obj, default=str))


@router.get("/config")
def tools_config() -> dict[str, Any]:
    """Read-only defaults and model parameters (for form labels / sliders)."""
    return {
        "cli_equivalent": {
            "modes": ["single", "recent", "batch"],
            "flags": [
                "--no-cache",
                "--no-visualize",
                "--no-news",
                "--news-days N",
                "--output DIR",
            ],
        },
        "news": {
            "lookback_days_default": config.NEWS_LOOKBACK_DAYS,
            "max_articles_default": config.NEWS_MAX_ARTICLES,
            "openai_news_model": config.OPENAI_NEWS_MODEL,
        },
        "technical": {
            "openai_tech_verdict_model": config.OPENAI_TECH_VERDICT_MODEL,
        },
        "market_model": {
            "estimation_window_days": config.ESTIMATION_WINDOW,
            "market_index": config.MARKET_INDEX,
            "min_trading_days": config.MIN_TRADING_DAYS,
        },
        "car_windows_days": list(config.CAR_WINDOWS or []),
        "significance_level": config.SIGNIFICANCE_LEVEL,
        "paths": {
            "output_default": str(ROOT / "output"),
            "pdf_download_dir": config.PDF_DOWNLOAD_DIR,
            "cache_dir": config.CACHE_DIR,
        },
    }


class PeadSingleRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    announcement_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD; omit to auto-detect latest earnings-style date",
    )
    visualize: bool = True
    use_cache: bool = True
    include_news: bool = True
    news_lookback_days: Optional[int] = Field(None, ge=1, le=730)
    news_max_articles: Optional[int] = Field(None, ge=1, le=500)
    output_dir: str = Field(default_factory=lambda: str(ROOT / "output"))


class PeadRecentRequest(BaseModel):
    top_n: int = Field(10, ge=1, le=100)
    visualize: bool = True
    use_cache: bool = True
    include_news: bool = True
    news_lookback_days: Optional[int] = Field(None, ge=1, le=730)
    news_max_articles: Optional[int] = Field(None, ge=1, le=500)
    output_dir: str = Field(default_factory=lambda: str(ROOT / "output"))


def _analyzer(use_cache: bool) -> PEADAnalyzer:
    return PEADAnalyzer(use_cache=use_cache)


def _resolve_single_date(body: PeadSingleRequest, analyzer: PEADAnalyzer) -> pd.Timestamp:
    sym = body.symbol.strip().upper()
    if body.announcement_date:
        return pd.to_datetime(body.announcement_date)
    dt = get_latest_announcement_date(sym, analyzer.data_manager)
    if dt is None:
        raise HTTPException(
            status_code=422,
            detail="Could not auto-detect announcement date; provide announcement_date (YYYY-MM-DD).",
        )
    return pd.Timestamp(dt)


@router.post("/run/single")
async def run_single(body: PeadSingleRequest) -> dict[str, Any]:
    """Run one symbol through the full PEAD pipeline (same as CLI single mode)."""
    sym = body.symbol.strip().upper()
    analyzer = _analyzer(body.use_cache)
    ann = _resolve_single_date(body, analyzer)
    out_base = Path(body.output_dir).expanduser().resolve()
    out_base.mkdir(parents=True, exist_ok=True)

    def _run():
        return analyzer.analyze_announcement(
            sym,
            ann.to_pydatetime(),
            visualize=body.visualize,
            output_dir=str(out_base),
            include_news=body.include_news,
            news_lookback_days=body.news_lookback_days,
            news_max_articles=body.news_max_articles,
        )

    result = await asyncio.to_thread(_run)
    compact = compact_pead_for_llm(result)
    return {
        "mode": "single",
        "success": result.get("success", False),
        "error": result.get("error"),
        "symbol": sym,
        "announcement_date_used": str(ann.date()),
        "output_dir": result.get("output_dir"),
        "result": compact,
    }


@router.post("/run/recent")
async def run_recent(body: PeadRecentRequest) -> dict[str, Any]:
    """Analyze top N recent NSE announcements (same as CLI recent mode)."""
    analyzer = _analyzer(body.use_cache)
    out_base = Path(body.output_dir).expanduser().resolve()
    out_base.mkdir(parents=True, exist_ok=True)

    def _run():
        return analyzer.analyze_recent_announcements(
            n=body.top_n,
            visualize=body.visualize,
            output_dir=str(out_base),
            include_news=body.include_news,
            news_lookback_days=body.news_lookback_days,
            news_max_articles=body.news_max_articles,
        )

    df, batch_root = await asyncio.to_thread(_run)

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
        "top_n": body.top_n,
        "row_count": len(rows),
        "batch_root": str(batch_root) if batch_root else None,
        "rows": rows,
    }


class ExecutionSnapshotRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    lookback_days: int = Field(200, ge=20, le=800)
    use_cache: bool = True


class YahooCalendarRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)


@router.post("/run/execution-snapshot")
async def run_execution_snapshot(body: ExecutionSnapshotRequest) -> dict[str, Any]:
    """
    Price + technicals + trade-readiness only (no PEAD/CAR/news).
    Isolated test surface for `fetch_light_trade_context`.
    """
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run():
        return fetch_light_trade_context(
            sym,
            analyzer.data_manager,
            lookback_calendar_days=int(body.lookback_days),
        )

    return await asyncio.to_thread(_run)


@router.post("/run/yahoo-calendar")
async def run_yahoo_calendar(body: YahooCalendarRequest) -> dict[str, Any]:
    """Best-effort Yahoo Finance calendar / earnings_dates for NSE symbol."""

    def _run():
        import yfinance as yf

        sym = body.symbol.strip().upper()
        t = yf.Ticker(f"{sym}.NS")
        out: dict[str, Any] = {"symbol": sym, "yahoo_ticker": f"{sym}.NS"}
        cal = getattr(t, "calendar", None)
        if cal is not None and hasattr(cal, "empty") and not cal.empty:
            out["calendar"] = cal.to_dict() if hasattr(cal, "to_dict") else str(cal)
        ed = getattr(t, "earnings_dates", None)
        if ed is not None and hasattr(ed, "empty") and not ed.empty:
            out["earnings_dates_head"] = ed.head(12).to_string()
        return out

    return await asyncio.to_thread(_run)


class SymbolToolRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    use_cache: bool = True


class DatedSymbolToolRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    announcement_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD; omit to auto-detect latest earnings-style date",
    )
    use_cache: bool = True


class TechnicalToolRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    use_cache: bool = True
    price_window: Literal["pead_event", "explicit_range"] = Field(
        "pead_event",
        description="pead_event: same calendar span as PEAD around an announcement. "
        "explicit_range: OHLCV between range_start and range_end (you set both).",
    )
    announcement_resolution: Literal["auto", "manual"] = Field(
        "auto",
        description="Only for price_window=pead_event: auto = detect latest earnings-style date; "
        "manual = use announcement_date.",
    )
    announcement_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD; required when price_window=pead_event and announcement_resolution=manual.",
    )
    range_start: Optional[str] = Field(
        None,
        description="YYYY-MM-DD; required when price_window=explicit_range (inclusive start).",
    )
    range_end: Optional[str] = Field(
        None,
        description="YYYY-MM-DD; required when price_window=explicit_range (inclusive end).",
    )
    include_chart: bool = Field(
        True,
        description="Include OHLCV bars, aligned indicator series, and pivot S/R for charting.",
    )
    include_ai_verdict: bool = Field(
        False,
        description="If true and OPENAI_API_KEY is set, append LLM research commentary (entry/exit framing; not advice).",
    )


class NewsToolRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    lookback_days: int = Field(90, ge=1, le=730)
    max_articles: int = Field(80, ge=1, le=500)
    use_cache: bool = True


class DocumentPdfRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    announcement_date: str = Field(..., description="YYYY-MM-DD")
    use_cache: bool = True


@router.post("/run/fundamentals")
async def run_fundamentals(body: SymbolToolRequest) -> dict[str, Any]:
    """Yahoo/NSE bundle + fundamental screening (pillar scores, ratios) — no PEAD event study."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run():
        bundle = analyzer.data_manager.get_company_fundamentals(sym)
        return analyzer.fundamental_analyzer.analyze(sym, bundle)

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/technical")
async def run_technical(body: TechnicalToolRequest) -> dict[str, Any]:
    """
    Post-event technical snapshot (RSI, MACD, MAs, ATR%). No implicit fallbacks — configure
    ``price_window`` and (for PEAD) ``announcement_resolution`` / dates explicitly.
    """
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    if body.price_window == "explicit_range":
        if not body.range_start or not body.range_end:
            raise HTTPException(
                status_code=422,
                detail="range_start and range_end (YYYY-MM-DD) are required when price_window is explicit_range.",
            )
    elif body.price_window == "pead_event":
        if body.announcement_resolution == "manual":
            if not body.announcement_date or not str(body.announcement_date).strip():
                raise HTTPException(
                    status_code=422,
                    detail="announcement_date is required when announcement_resolution is manual.",
                )

    def _run() -> dict[str, Any]:
        stock_data: Optional[pd.DataFrame] = None
        out_base: dict[str, Any] = {
            "symbol": sym,
            "price_window": body.price_window,
        }

        if body.price_window == "explicit_range":
            start_dt = pd.to_datetime(body.range_start).to_pydatetime()
            end_dt = pd.to_datetime(body.range_end).to_pydatetime()
            if start_dt > end_dt:
                return {
                    "success": False,
                    "error": "range_start must be on or before range_end.",
                    **out_base,
                    "range_start": body.range_start,
                    "range_end": body.range_end,
                }
            stock_data = analyzer.data_manager.get_stock_data(sym, start_dt, end_dt)
            out_base["range_start"] = body.range_start
            out_base["range_end"] = body.range_end
        else:
            out_base["announcement_resolution"] = body.announcement_resolution
            if body.announcement_resolution == "manual":
                ann = pd.to_datetime(body.announcement_date)
            else:
                req = PeadSingleRequest(
                    symbol=sym,
                    announcement_date=None,
                    use_cache=body.use_cache,
                )
                ann = _resolve_single_date(req, analyzer)
            ann_dt = ann.to_pydatetime()
            stock_data = analyzer.data_manager.get_stock_data_for_event_window(sym, ann_dt)
            out_base["announcement_date_used"] = str(ann.date())

        if stock_data is None or stock_data.empty:
            err = (
                f"No OHLCV for {sym} in the requested window from NSE/Yahoo. "
                "Widen the explicit range or verify the symbol / announcement date."
            )
            if body.price_window == "pead_event":
                err += f" (PEAD window around {out_base.get('announcement_date_used', '?')})"
            return {"success": False, "error": err, **out_base}

        idx = stock_data.index
        anchor = pd.Timestamp(idx[-1])
        ta = analyzer.technical_analyzer.analyze(
            stock_data,
            anchor,
            symbol=sym,
            include_chart_payload=body.include_chart,
        )
        return {
            "success": True,
            **out_base,
            "ohlc_index_start": str(idx.min())[:10],
            "ohlc_index_end": str(idx.max())[:10],
            "technical_analysis": ta,
        }

    out = await asyncio.to_thread(_run)
    if out.get("success") is False:
        raise HTTPException(status_code=422, detail=out.get("error", "Technical run failed"))
    if body.include_ai_verdict:
        verdict = await asyncio.to_thread(generate_technical_verdict, out)
        out["research_verdict"] = verdict
    return _json_safe(out)


@router.post("/run/news")
async def run_news_layer(body: NewsToolRequest) -> dict[str, Any]:
    """Headline collection + TextBlob / optional OpenAI sentiment — no PEAD."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run() -> dict[str, Any]:
        return run_news_sentiment_layer(
            analyzer,
            sym,
            lookback_days=int(body.lookback_days),
            max_articles=int(body.max_articles),
        )

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/scoring")
async def run_scoring_stack(body: DatedSymbolToolRequest) -> dict[str, Any]:
    """CARs + five PEAD component scores + composite — no technicals, news, or files."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()
    req = PeadSingleRequest(
        symbol=sym,
        announcement_date=body.announcement_date,
        use_cache=body.use_cache,
    )
    ann = _resolve_single_date(req, analyzer)

    def _run():
        return analyzer.analyze_scoring_only(sym, ann.to_pydatetime())

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/trade-readiness")
async def run_trade_readiness_isolated(body: ExecutionSnapshotRequest) -> dict[str, Any]:
    """
    Trade readiness pillars only (liquidity, vol regime, alignment, model fit).
    Uses price-window technicals + light placeholders for fundamentals/news/PEAD rating.
    """
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run() -> dict[str, Any]:
        full = fetch_light_trade_context(
            sym,
            analyzer.data_manager,
            lookback_calendar_days=int(body.lookback_days),
        )
        if not full.get("success"):
            return full
        return {
            "success": True,
            "symbol": sym,
            "trade_context": full.get("trade_context"),
            "note": full.get("note"),
        }

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/document-pdf")
async def run_document_pdf(body: DocumentPdfRequest) -> dict[str, Any]:
    """Parse an announcement PDF already on disk (NSE downloader naming convention)."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()
    ann = pd.to_datetime(body.announcement_date)

    def _run() -> dict[str, Any]:
        p = analyzer.pdf_downloader.get_pdf_path(sym, ann.to_pydatetime())
        if not p or not p.exists():
            return {
                "success": False,
                "error": (
                    f"No PDF found for {sym} on {body.announcement_date}. "
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

    return _json_safe(await asyncio.to_thread(_run))
