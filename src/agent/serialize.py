"""
Trim PEAD analyzer output for LLM context windows.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def compact_pead_for_llm(result: Dict[str, Any], max_brief_chars: int = 14000) -> Dict[str, Any]:
    """JSON-serializable subset for agents and streaming UI."""
    if not result.get("success"):
        return {"success": False, "error": result.get("error")}

    brief = result.get("research_brief") or ""
    if brief and len(brief) > max_brief_chars:
        brief = brief[:max_brief_chars] + "\n...[truncated]"

    fa = result.get("fundamental_analysis")
    fa_trim = None
    if isinstance(fa, dict):
        ratios = fa.get("ratios") if isinstance(fa.get("ratios"), dict) else {}
        headline_keys = (
            "pe_trailing",
            "pe_forward",
            "peg",
            "price_to_book",
            "roe",
            "roa",
            "debt_to_equity",
            "current_ratio",
            "operating_margin",
            "profit_margin",
        )
        headline_ratios = {
            k: ratios.get(k) for k in headline_keys if ratios.get(k) is not None
        }
        fa_trim = {
            "stance": fa.get("stance"),
            "scores": fa.get("scores"),
            "headline_ratios": headline_ratios or None,
        }

    out: Dict[str, Any] = {
        "success": True,
        "symbol": result.get("symbol"),
        "announcement_date": str(result.get("announcement_date")),
        "analysis_period_start": result.get("analysis_period_start"),
        "analysis_period_end": result.get("analysis_period_end"),
        "output_dir": result.get("output_dir"),
        "pipeline_kind": result.get("pipeline_kind"),
        "price_window_source": result.get("price_window_source"),
        "price_fetch_calendar_start": result.get("price_fetch_calendar_start"),
        "price_fetch_calendar_end": result.get("price_fetch_calendar_end"),
        "fundamental_analysis": fa_trim,
        "technical_analysis": result.get("technical_analysis"),
        "technical_include_ai_verdict": result.get("technical_include_ai_verdict"),
        "technical_tool_response": result.get("technical_tool_response"),
        "news_sentiment": result.get("news_sentiment"),
        "news_tool_response": result.get("news_tool_response"),
        "market_sentiment": result.get("market_sentiment"),
        "market_tool_response": result.get("market_tool_response"),
        "trade_context": result.get("trade_context"),
        "research_desk": result.get("research_desk"),
        "pipeline_trace": result.get("pipeline_trace"),
        "equity_pipeline_stages": result.get("equity_pipeline_stages"),
    }
    if brief:
        out["research_brief_excerpt"] = brief
    for k in ("composite_score", "car_data", "market_model", "synthesis"):
        if result.get(k) is not None:
            out[k] = result[k]
    return out


def json_dumps_safe(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)
