"""Ordered stage execution with timing trace."""

from __future__ import annotations

import logging
import time
from typing import Callable, List, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.equity_research_pipeline.context import EquityResearchRunContext
    from src.equity_research_pipeline.protocols import EquityResearchAnalyzerServices

PIPELINE_VERSION = "1.0-equity-research-tools"

StageFn = Callable[["EquityResearchRunContext", "EquityResearchAnalyzerServices"], None]
StageSpec = Tuple[str, StageFn]


def execute_pipeline(
    ctx: EquityResearchRunContext,
    analyzer: EquityResearchAnalyzerServices,
    stages: Sequence[StageSpec],
    log: logging.Logger | logging.LoggerAdapter,
    *,
    trace_key: str = "pipeline_trace",
) -> None:
    """
    Run each stage in order. Mutates ``ctx.results`` / ``ctx.workspace``.

    Appends ``{stage, duration_ms, ok}`` to ``ctx.results[trace_key]``.
    """
    trace: List[dict] = []
    ctx.results["pipeline_version"] = PIPELINE_VERSION
    ctx.results[trace_key] = trace

    for stage_name, stage_fn in stages:
        t0 = time.perf_counter()
        log.info(
            "equity_research.pipeline stage=start run_id=%s symbol=%s stage=%s",
            ctx.run_id,
            ctx.symbol,
            stage_name,
            extra={"equity_stage": stage_name, "equity_run_id": ctx.run_id, "equity_symbol": ctx.symbol},
        )
        try:
            stage_fn(ctx, analyzer)
        except Exception:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            trace.append({"stage": stage_name, "duration_ms": elapsed_ms, "ok": False})
            log.exception(
                "equity_research.pipeline stage=failed run_id=%s symbol=%s stage=%s duration_ms=%s",
                ctx.run_id,
                ctx.symbol,
                stage_name,
                elapsed_ms,
                extra={"equity_stage": stage_name, "equity_run_id": ctx.run_id, "equity_symbol": ctx.symbol},
            )
            raise
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        trace.append({"stage": stage_name, "duration_ms": elapsed_ms, "ok": True})
        log.info(
            "equity_research.pipeline stage=done run_id=%s symbol=%s stage=%s duration_ms=%s",
            ctx.run_id,
            ctx.symbol,
            stage_name,
            elapsed_ms,
            extra={"equity_stage": stage_name, "equity_run_id": ctx.run_id, "equity_symbol": ctx.symbol},
        )
