"""
Direct PEAD runs from the /tools UI — same knobs as the CLI (no LLM required).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agent.announcements import get_latest_announcement_date
from src.agent.serialize import compact_pead_for_llm
from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.config import config
from src.news.layer import run_news_sentiment_layer
from src.tools.executions import (
    execute_document_pdf,
    execute_execution_snapshot,
    execute_fundamentals,
    execute_recent_announcements,
    execute_scoring_only,
    execute_technical,
    execute_trade_readiness_isolated,
    execute_yahoo_calendar,
)
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
            "max_scrape_default": 25,
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
        return execute_recent_announcements(
            analyzer,
            body.top_n,
            visualize=body.visualize,
            output_dir=str(out_base),
            include_news=body.include_news,
            news_lookback_days=body.news_lookback_days,
            news_max_articles=body.news_max_articles,
        )

    return _json_safe(await asyncio.to_thread(_run))


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
        return execute_execution_snapshot(analyzer, sym, body.lookback_days)

    return await asyncio.to_thread(_run)


@router.post("/run/yahoo-calendar")
async def run_yahoo_calendar(body: YahooCalendarRequest) -> dict[str, Any]:
    """Best-effort Yahoo Finance calendar / earnings_dates for NSE symbol."""

    def _run():
        return execute_yahoo_calendar(body.symbol)

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
    end_date: Optional[str] = Field(
        None,
        description="ISO date YYYY-MM-DD; end of news window (default: now UTC)",
    )
    scrape_bodies: bool = Field(
        True,
        description="Fetch full article HTML for first N URLs (trafilatura)",
    )
    max_scrape: int = Field(
        25,
        ge=0,
        le=80,
        description="Max articles to scrape for body text (0 = headlines/snippets only)",
    )


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
        return execute_fundamentals(analyzer, sym)

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
        return execute_technical(
            analyzer,
            symbol=sym,
            price_window=body.price_window,
            announcement_resolution=body.announcement_resolution,
            announcement_date=body.announcement_date,
            range_start=body.range_start,
            range_end=body.range_end,
            include_chart=body.include_chart,
            include_ai_verdict=body.include_ai_verdict,
        )

    out = await asyncio.to_thread(_run)
    if out.get("success") is False:
        raise HTTPException(status_code=422, detail=out.get("error", "Technical run failed"))
    return _json_safe(out)


@router.post("/run/news")
async def run_news_layer(body: NewsToolRequest) -> dict[str, Any]:
    """Headlines + optional full-page scrape + TextBlob / optional OpenAI sentiment — no PEAD."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    end_dt: Optional[datetime] = None
    if body.end_date:
        raw = body.end_date.strip()
        try:
            end_dt = datetime.fromisoformat(raw)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="end_date must be YYYY-MM-DD or full ISO datetime",
            ) from None

    def _run() -> dict[str, Any]:
        return run_news_sentiment_layer(
            analyzer,
            sym,
            lookback_days=int(body.lookback_days),
            max_articles=int(body.max_articles),
            end_date=end_dt,
            scrape_bodies=bool(body.scrape_bodies),
            max_scrape=int(body.max_scrape),
        )

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/scoring")
async def run_scoring_stack(body: DatedSymbolToolRequest) -> dict[str, Any]:
    """CARs + five PEAD component scores + composite — no technicals, news, or files."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run():
        return execute_scoring_only(analyzer, sym, body.announcement_date)

    out = await asyncio.to_thread(_run)
    return _json_safe(out)


@router.post("/run/trade-readiness")
async def run_trade_readiness_isolated(body: ExecutionSnapshotRequest) -> dict[str, Any]:
    """
    Trade readiness pillars only (liquidity, vol regime, alignment, model fit).
    Uses price-window technicals + light placeholders for fundamentals/news/PEAD rating.
    """
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run() -> dict[str, Any]:
        return execute_trade_readiness_isolated(analyzer, sym, body.lookback_days)

    return _json_safe(await asyncio.to_thread(_run))


@router.post("/run/document-pdf")
async def run_document_pdf(body: DocumentPdfRequest) -> dict[str, Any]:
    """Parse an announcement PDF already on disk (NSE downloader naming convention)."""
    analyzer = _analyzer(body.use_cache)
    sym = body.symbol.strip().upper()

    def _run() -> dict[str, Any]:
        return execute_document_pdf(analyzer, sym, body.announcement_date)

    out = await asyncio.to_thread(_run)
    return _json_safe(out)
