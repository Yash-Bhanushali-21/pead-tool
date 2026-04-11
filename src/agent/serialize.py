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
    if len(brief) > max_brief_chars:
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

    return {
        "success": True,
        "symbol": result.get("symbol"),
        "announcement_date": str(result.get("announcement_date")),
        "output_dir": result.get("output_dir"),
        "composite_score": result.get("composite_score"),
        "car_data": result.get("car_data"),
        "market_model": result.get("market_model"),
        "synthesis": result.get("synthesis"),
        "research_brief_excerpt": brief,
        "fundamental_analysis": fa_trim,
        "technical_analysis": result.get("technical_analysis"),
        "news_sentiment": result.get("news_sentiment"),
        "trade_context": result.get("trade_context"),
    }


def json_dumps_safe(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)
