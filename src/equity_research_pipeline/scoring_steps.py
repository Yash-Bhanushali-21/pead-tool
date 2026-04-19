"""PEAD scoring-only path (CAR + pillars + composite) for ``/api/tools/run/scoring`` — separate from equity research full run."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import pandas as pd

from src.config.config import config
from src.equity_research_pipeline.context import EquityResearchRunContext
from src.equity_research_pipeline.options import EquityResearchRunOptions
from src.utils.time_compat import to_naive_utc_datetime
from src.models.abnormal_returns import AbnormalReturns
from src.models.car import CumulativeAbnormalReturns
from src.models.market_model import MarketModel

if TYPE_CHECKING:
    from src.equity_research_pipeline.protocols import EquityResearchAnalyzerServices

logger = logging.getLogger(__name__)


def scoring_step_company_and_pdf_meta(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    company_info = an.data_manager.get_company_fundamentals(ctx.symbol)
    ctx.workspace["company_info"] = company_info
    assert ctx.announcement_date is not None
    pdf_analysis = an._analyze_announcement_pdf(ctx.symbol, ctx.announcement_date)
    ctx.workspace["pdf_analysis"] = pdf_analysis
    ctx.results["pdf_analysis_meta"] = {
        "text_chars": len((pdf_analysis.get("text") or "")),
        "metric_keys": list((pdf_analysis.get("metrics") or {}).keys())
        if isinstance(pdf_analysis.get("metrics"), dict)
        else [],
        "has_guidance": bool((pdf_analysis.get("guidance") or {}).get("has_guidance")),
    }


def scoring_step_market_model(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    stock_data: pd.DataFrame = ctx.workspace["stock_data"]
    market_data: pd.DataFrame = ctx.workspace["market_data"]
    market_model = MarketModel()
    model_params = market_model.estimate(
        stock_data["Return"],
        market_data["Return"],
        ctx.announcement_date,
    )
    ctx.workspace["market_model_obj"] = market_model
    ctx.results["market_model"] = model_params


def scoring_step_ar_car(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    stock_data: pd.DataFrame = ctx.workspace["stock_data"]
    market_data: pd.DataFrame = ctx.workspace["market_data"]
    market_model: MarketModel = ctx.workspace["market_model_obj"]
    assert ctx.announcement_date is not None
    ar_calculator = AbnormalReturns(market_model)
    ar_data = ar_calculator.calculate(
        stock_data["Return"],
        market_data["Return"],
        ctx.announcement_date,
        event_window=(0, max(config.CAR_WINDOWS)),
        estimate_model=False,
    )
    ar_summary: Dict[str, Any] = {"rows": 0, "tail": []}
    if isinstance(ar_data, pd.DataFrame) and not ar_data.empty and "AR" in ar_data.columns:
        ar_summary["rows"] = int(len(ar_data))
        tail = ar_data.tail(8)
        ar_summary["tail"] = tail.reset_index().to_dict(orient="records")
    ctx.results["abnormal_returns_summary"] = ar_summary

    car_calculator = CumulativeAbnormalReturns(ar_calculator)
    model_params = ctx.results["market_model"]
    n_obs = int(model_params.get("n_observations") or 0)
    est_df = max(n_obs - 2, 1)
    car_data = car_calculator.calculate(
        ar_data,
        estimation_residual_std=model_params.get("residual_std"),
        estimation_t_df=est_df,
    )
    ctx.workspace["ar_data"] = ar_data
    ctx.results["car_data"] = car_data


def scoring_step_scores_and_composite(ctx: EquityResearchRunContext, an: EquityResearchAnalyzerServices) -> None:
    pdf_analysis: Dict[str, Any] = ctx.workspace["pdf_analysis"]
    stock_data: pd.DataFrame = ctx.workspace["stock_data"]
    market_data: pd.DataFrame = ctx.workspace["market_data"]
    car_data: Dict[str, Any] = ctx.results["car_data"]
    company_info: Dict[str, Any] = ctx.workspace["company_info"]
    assert ctx.announcement_date is not None
    scores, quality_meta = an._calculate_all_scores(
        ctx.symbol,
        pdf_analysis,
        stock_data,
        market_data,
        car_data,
        company_info,
        ctx.announcement_date,
    )
    ctx.results["scores"] = scores
    model_params = ctx.results["market_model"]
    data_quality: Dict[str, Any] = {
        **quality_meta,
        "r_squared": model_params.get("r_squared"),
        "residual_std": model_params.get("residual_std"),
        "n_observations": model_params.get("n_observations"),
    }
    composite = an.composite_scorer.calculate_composite_score(
        scores["earnings_surprise"],
        scores["price_reaction"],
        scores["drift_confirmation"],
        scores["earnings_quality"],
        scores["contextual"],
        data_quality=data_quality,
    )
    ctx.results["composite_score"] = composite


def new_scoring_context(symbol: str, announcement_date: Any) -> EquityResearchRunContext:
    sym = symbol.strip().upper()
    ad = to_naive_utc_datetime(announcement_date)
    return EquityResearchRunContext(
        symbol=sym,
        analysis_start=ad,
        analysis_end=ad,
        options=EquityResearchRunOptions(
            visualize=False,
            output_dir=None,
            include_news=False,
        ),
        announcement_date=ad,
        results={
            "symbol": sym,
            "analysis_period_start": ad.date().isoformat(),
            "analysis_period_end": ad.date().isoformat(),
            "announcement_date": ad,
            "success": False,
            "error": None,
            "mode": "scoring_only",
        },
    )


SCORING_ONLY_STEPS: List[Tuple[str, Any]] = [
    ("company_and_pdf_meta", scoring_step_company_and_pdf_meta),
    ("market_model", scoring_step_market_model),
    ("abnormal_returns_and_car", scoring_step_ar_car),
    ("scores_and_composite", scoring_step_scores_and_composite),
]
