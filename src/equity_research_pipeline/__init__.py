"""
Equity research orchestration: explicit stages, run-scoped logging, Tools-backed executors.

``StockAnalyzer.analyze_equity_research`` runs an ordered stage list (default: all stages in
``full_run_steps.EQUITY_RESEARCH_FULL_STAGES``); optional ``pipeline_stages`` on the request selects a subset.
``analyze_announcement`` → expanded window uses the same path with full stages.
``analyze_scoring_only`` still runs ``SCORING_ONLY_STEPS`` (PEAD CAR stack) for the scoring tool route.
"""

from src.equity_research_pipeline.context import EquityResearchRunContext, new_equity_run_context
from src.equity_research_pipeline.options import EquityResearchRunOptions
from src.equity_research_pipeline.runner import PIPELINE_VERSION, execute_pipeline

__all__ = [
    "EquityResearchRunContext",
    "EquityResearchRunOptions",
    "PIPELINE_VERSION",
    "execute_pipeline",
    "new_equity_run_context",
]
