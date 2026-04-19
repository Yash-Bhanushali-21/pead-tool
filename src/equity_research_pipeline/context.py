"""Mutable run bag: ``results`` (API-facing) and ``workspace`` (DataFrames, etc.)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from src.equity_research_pipeline.options import EquityResearchRunOptions
from src.utils.time_compat import to_naive_utc_datetime


def _short_run_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class EquityResearchRunContext:
    """One symbol + explicit analysis calendar window (inclusive OHLCV / news / technical)."""

    symbol: str
    analysis_start: datetime
    analysis_end: datetime
    options: EquityResearchRunOptions
    results: Dict[str, Any]
    workspace: Dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=_short_run_id)
    """Set for scoring-only / legacy chart paths (e.g. vertical line = last bar ≈ window end)."""
    announcement_date: Optional[datetime] = None


def new_equity_run_context(
    symbol: str,
    analysis_start: datetime,
    analysis_end: datetime,
    options: EquityResearchRunOptions,
) -> EquityResearchRunContext:
    sym = symbol.strip().upper()
    a0 = to_naive_utc_datetime(analysis_start)
    a1 = to_naive_utc_datetime(analysis_end)
    return EquityResearchRunContext(
        symbol=sym,
        analysis_start=a0,
        analysis_end=a1,
        options=options,
        announcement_date=a1,
        results={
            "symbol": sym,
            "analysis_period_start": a0.date().isoformat(),
            "analysis_period_end": a1.date().isoformat(),
            "announcement_date": a1,
            "timestamp": datetime.now(),
            "success": False,
            "error": None,
            "output_dir": None,
            "pipeline_kind": "equity_research",
        },
    )
