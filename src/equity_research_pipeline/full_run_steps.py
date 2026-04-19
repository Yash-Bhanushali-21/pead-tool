"""
Equity research full run: single source of truth via Tools-layer executors.

No CAR / component scores / composite / research-brief assembly in this path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import pandas as pd

from src.config.config import config
from src.trade_context.trade_readiness import compute_trade_context

if TYPE_CHECKING:
    from src.equity_research_pipeline.context import EquityResearchRunContext
    from src.equity_research_pipeline.protocols import EquityResearchAnalyzerServices

logger = logging.getLogger(__name__)


def stage_fetch_price_window(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    """
    Load OHLCV for ``[ctx.analysis_start, ctx.analysis_end]`` inclusive (calendar window set at run
    entry). All later stages reuse this frame (technical via preloaded OHLCV; trade context).
    """
    a0, a1 = ctx.analysis_start, ctx.analysis_end
    if a0 > a1:
        raise ValueError("analysis_start must be on or before analysis_end")
    ctx.results["price_fetch_calendar_start"] = a0.date().isoformat()
    ctx.results["price_fetch_calendar_end"] = a1.date().isoformat()
    logger.info(
        "equity_research.fetch_price_window run=%s symbol=%s calendar_start=%s calendar_end=%s",
        ctx.run_id,
        ctx.symbol,
        ctx.results["price_fetch_calendar_start"],
        ctx.results["price_fetch_calendar_end"],
    )
    stock_data = an.data_manager.get_stock_data(ctx.symbol, a0, a1)
    if stock_data is None or stock_data.empty:
        msg = (
            f"No OHLCV for {ctx.symbol} between {ctx.results['price_fetch_calendar_start']} and "
            f"{ctx.results['price_fetch_calendar_end']}. NSE/Yahoo returned no usable daily prices; "
            "pipeline stopped before later stages."
        )
        logger.error("equity_research.fetch_price_window: %s", msg)
        raise ValueError(msg)
    # Clip to the requested **calendar** window so charts/tools never show bars outside UI range.
    cal_s = pd.Timestamp(a0.date()).normalize()
    cal_e = pd.Timestamp(a1.date()).normalize()
    dti = pd.DatetimeIndex(stock_data.index)
    if dti.tz is not None:
        dti = dti.tz_convert("UTC").tz_localize(None)
    norm = dti.normalize()
    mask = (norm >= cal_s) & (norm <= cal_e)
    stock_data = stock_data.loc[mask].copy()
    if stock_data.empty:
        msg = (
            f"No OHLCV rows for {ctx.symbol} after clipping to {cal_s.date()} .. {cal_e.date()} "
            "(vendor may have returned only dates outside this span)."
        )
        logger.error("equity_research.fetch_price_window: %s", msg)
        raise ValueError(msg)
    ctx.workspace["stock_data"] = stock_data
    ctx.results["data_points"] = int(len(stock_data))
    ctx.results["price_window_source"] = "explicit_range"
    idx = stock_data.index
    idx_min = pd.Timestamp(idx.min()).isoformat()
    idx_max = pd.Timestamp(idx.max()).isoformat()
    logger.info(
        "equity_research.fetch_price_window run=%s symbol=%s rows=%d ohlcv_index_min=%s "
        "ohlcv_index_max=%s",
        ctx.run_id,
        ctx.symbol,
        len(stock_data),
        idx_min,
        idx_max,
    )


def stage_resolve_output_dir(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    opts = ctx.options
    if not opts.output_dir:
        return
    from src.utils.run_output import resolve_run_output_directory

    stock_data: pd.DataFrame = ctx.workspace["stock_data"]
    resolved_out = resolve_run_output_directory(
        opts.output_dir,
        ctx.symbol,
        ctx.analysis_end,
        stock_data.index,
        run_timestamp=opts.run_timestamp,
    )
    resolved_out.mkdir(parents=True, exist_ok=True)
    out = str(resolved_out)
    ctx.results["output_dir"] = out
    logger.info("Run output directory: %s", out)


def stage_run_fundamentals_tool(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    from src.tools.executions import execute_fundamentals

    fa = execute_fundamentals(an, ctx.symbol)
    ctx.results["fundamental_analysis"] = fa
    output_dir = ctx.results.get("output_dir")
    if not output_dir:
        return
    outp = Path(output_dir)
    outp.mkdir(parents=True, exist_ok=True)
    sym = ctx.symbol
    with open(outp / f"{sym}_fundamentals.txt", "w", encoding="utf-8") as fh:
        fh.write(an.fundamental_analyzer.format_report(fa))
    with open(outp / f"{sym}_fundamentals.json", "w", encoding="utf-8") as fh:
        fh.write(an.fundamental_analyzer.to_json(fa))
    if ctx.options.visualize:
        an.visualizer.plot_fundamental_pillars(
            fa,
            save_path=str(outp / f"{sym}_fundamentals.png"),
        )


def stage_run_technical_tool(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    from src.tools.executions import execute_technical

    o = ctx.options
    sd = ctx.workspace.get("stock_data")
    if not isinstance(sd, pd.DataFrame) or sd.empty:
        ctx.results["technical_tool_response"] = {"success": False, "error": "Missing OHLCV workspace"}
        ctx.results["technical_analysis"] = {}
        return
    resp = execute_technical(
        an,
        symbol=ctx.symbol,
        preloaded_ohlcv=sd,
        include_chart=o.technical_include_chart,
        include_ai_verdict=o.technical_include_ai_verdict,
    )
    ctx.results["technical_tool_response"] = resp
    if resp.get("success"):
        ctx.results["technical_analysis"] = resp.get("technical_analysis") or {}
    else:
        ctx.results["technical_analysis"] = {}
        ctx.results["technical_tool_error"] = resp.get("error")
    output_dir = ctx.results.get("output_dir")
    if output_dir and resp.get("success"):
        outp = Path(output_dir)
        with open(outp / f"{ctx.symbol}_technical.json", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(ctx.results["technical_analysis"], indent=2, default=str))


def stage_run_news_tool(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    if not ctx.options.include_news:
        ctx.results["news_sentiment"] = None
        return
    from src.news.layer import run_news_sentiment_layer

    o = ctx.options
    mx = o.news_max_articles if o.news_max_articles is not None else config.NEWS_MAX_ARTICLES
    layer_out = run_news_sentiment_layer(
        an,
        ctx.symbol,
        lookback_days=int(config.NEWS_LOOKBACK_DAYS),
        max_articles=int(mx),
        window_start=ctx.analysis_start,
        window_end=ctx.analysis_end,
        scrape_bodies=o.news_scrape_bodies,
        max_scrape=int(o.news_max_scrape),
        include_ai_digest=o.include_symbol_news_ai_digest,
    )
    ctx.results["news_tool_response"] = layer_out
    ctx.results["news_sentiment"] = layer_out.get("news_sentiment") if isinstance(layer_out, dict) else None
    output_dir = ctx.results.get("output_dir")
    if output_dir:
        outp = Path(output_dir)
        arts = (layer_out.get("articles_preview") if isinstance(layer_out, dict) else None) or []
        if isinstance(arts, list) and arts:
            with open(outp / f"{ctx.symbol}_news_preview.json", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(arts[:200], indent=2, default=str, ensure_ascii=False))
        with open(outp / f"{ctx.symbol}_news_layer.json", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(layer_out, indent=2, default=str))


def stage_run_market_sentiment_tool(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    if not ctx.options.include_market_sentiment:
        ctx.results["market_sentiment"] = None
        ctx.results["market_tool_response"] = None
        return
    from src.news.market_sentiment_layer import run_market_sentiment_layer

    bundle = an.data_manager.get_company_fundamentals(ctx.symbol)
    company_name = str(bundle.get("company_name") or ctx.symbol).strip()
    mx = int(ctx.options.market_sentiment_max_articles)
    layer_out = run_market_sentiment_layer(
        an,
        ctx.symbol,
        company_name,
        window_start=ctx.analysis_start,
        window_end=ctx.analysis_end,
        max_articles=max(10, mx),
        preview_limit=min(40, max(10, mx)),
        scrape_bodies=ctx.options.news_scrape_bodies,
        max_scrape=min(22, ctx.options.news_max_scrape),
        include_ai_digest=ctx.options.include_market_news_ai_digest,
    )
    ctx.results["market_tool_response"] = layer_out
    ctx.results["market_sentiment"] = (
        layer_out.get("market_sentiment") if isinstance(layer_out, dict) else None
    )
    output_dir = ctx.results.get("output_dir")
    if output_dir:
        outp = Path(output_dir)
        arts = (layer_out.get("articles_preview") if isinstance(layer_out, dict) else None) or []
        if isinstance(arts, list) and arts:
            with open(outp / f"{ctx.symbol}_market_news_preview.json", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(arts[:200], indent=2, default=str, ensure_ascii=False))
        with open(outp / f"{ctx.symbol}_market_sentiment_layer.json", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(layer_out, indent=2, default=str))


def stage_run_trade_context(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    stock_data: pd.DataFrame = ctx.workspace["stock_data"]
    probe: Dict[str, Any] = {
        "fundamental_analysis": ctx.results.get("fundamental_analysis") or {},
        "technical_analysis": ctx.results.get("technical_analysis") or {},
        "news_sentiment": ctx.results.get("news_sentiment") or {},
        "market_sentiment": ctx.results.get("market_sentiment") or {},
        "composite_score": {},
        "market_model": {},
    }
    try:
        ctx.results["trade_context"] = compute_trade_context(probe, stock_data)
    except Exception as e:
        logger.warning("Trade context failed: %s", e)
        ctx.results["trade_context"] = {"error": str(e), "trade_readiness_score_0_100": None}


def stage_run_research_desk(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    """Single LLM pass over the consolidated bundle (does not fail the pipeline on model errors)."""
    if not ctx.options.include_desk_insight:
        ctx.results["research_desk"] = {
            "skipped": True,
            "reason": "Research desk insight disabled for this run.",
        }
        return
    from src.equity_research_pipeline.desk_insight import (
        build_equity_research_bundle,
        run_equity_desk_insight,
    )

    try:
        bundle = build_equity_research_bundle(ctx)
        ctx.results["research_desk"] = run_equity_desk_insight(bundle)
    except Exception as e:
        logger.warning("Research desk stage failed: %s", e)
        ctx.results["research_desk"] = {"error": str(e)}

    out = ctx.results.get("research_desk")
    output_dir = ctx.results.get("output_dir")
    if (
        output_dir
        and isinstance(out, dict)
        and isinstance(out.get("markdown"), str)
        and out["markdown"].strip()
    ):
        outp = Path(output_dir)
        outp.mkdir(parents=True, exist_ok=True)
        (outp / f"{ctx.symbol}_research_desk.md").write_text(
            out["markdown"],
            encoding="utf-8",
        )


EQUITY_RESEARCH_FULL_STAGES: List[Tuple[str, Any]] = [
    ("fetch_price_window", stage_fetch_price_window),
    ("resolve_output_dir", stage_resolve_output_dir),
    ("run_fundamentals_tool", stage_run_fundamentals_tool),
    ("run_technical_tool", stage_run_technical_tool),
    ("run_news_tool", stage_run_news_tool),
    ("run_market_sentiment_tool", stage_run_market_sentiment_tool),
    ("run_trade_context", stage_run_trade_context),
    ("run_research_desk", stage_run_research_desk),
]

EQUITY_PIPELINE_STAGE_IDS: Tuple[str, ...] = tuple(n for n, _ in EQUITY_RESEARCH_FULL_STAGES)

_STAGES_NEEDING_OHLCV_IN_WORKSPACE = frozenset(
    {
        "resolve_output_dir",
        "run_technical_tool",
        "run_trade_context",
    }
)


def select_equity_research_stages(opts: Any) -> List[Tuple[str, Any]]:
    """
    Ordered subset of :data:`EQUITY_RESEARCH_FULL_STAGES` from ``opts.pipeline_stages``.

    When ``pipeline_stages`` is ``None`` or empty, returns the full list. Otherwise filters to
    requested ids (preserving canonical order) and **prepends** ``fetch_price_window`` when any
    selected stage needs ``ctx.workspace['stock_data']``. If ``resolve_output_dir`` is selected,
    ``fetch_price_window`` is prepended when missing (resolve reads OHLCV from the workspace).
    """
    from src.equity_research_pipeline.options import EquityResearchRunOptions as _ERO

    if not isinstance(opts, _ERO):
        raise TypeError("opts must be EquityResearchRunOptions")

    raw = opts.pipeline_stages
    if raw is None or len(raw) == 0:
        return list(EQUITY_RESEARCH_FULL_STAGES)

    known = {n for n, _ in EQUITY_RESEARCH_FULL_STAGES}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown pipeline_stages: {sorted(unknown)}")

    chosen: set[str] = set(raw)
    needs_ws = chosen & _STAGES_NEEDING_OHLCV_IN_WORKSPACE
    if needs_ws and "fetch_price_window" not in chosen:
        chosen.add("fetch_price_window")
    if "resolve_output_dir" in chosen and "fetch_price_window" not in chosen:
        chosen.add("fetch_price_window")

    return [(n, fn) for n, fn in EQUITY_RESEARCH_FULL_STAGES if n in chosen]
