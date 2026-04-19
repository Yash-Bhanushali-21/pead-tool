"""
Post-pipeline research desk: single OpenAI call with the full equity-research bundle.

Orchestration stays in ``full_run_steps`` — this module only shapes context + calls the model.
Output is research commentary only (not regulated research, not investment advice).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List

from src.config.config import CONFIG, config
from src.technical.ai_verdict import _compact_technical_for_llm

if TYPE_CHECKING:
    from src.equity_research_pipeline.context import EquityResearchRunContext

logger = logging.getLogger(__name__)

_SYSTEM = """You are a senior **internal** equities and execution-research analyst covering Indian NSE cash equities. You write for a professional risk desk: precise, skeptical, **risk-first**, explicit about **assumptions and data limits**.

You do **not** give investment advice, do not solicit trades, and do **not** claim affiliation with any asset manager or bank. You may discuss **hypothetical** next-session scenarios as **conditional** research only.

You will receive structured JSON from our tools (fundamentals snapshot, technicals with levels, news sentiment summary + article list metadata, trade-readiness style context, and the analysis date window). Treat missing fields as unknown.

## Required output (Markdown, use these headings in order)

### Executive synthesis
6–10 sentences integrating fundamentals quality, technical posture, news tone, and liquidity/volatility cues. Separate **fact** (from payload) from **inference**.

### Key risks and invalidations
Bullet list: what would prove this synthesis wrong (price, flow, headline, filing risk).

### Next session — conditional playbook (research only)
Numbered items for the **first opening session after the analysis window end**:
- Scenarios (gap up / flat / gap down) with **if–then** framing only.
- Reference **zones** from payload (supports/resistances) as **reference bands**, not guarantees.
- Mention **session risk** (slippage, auction, event calendar unknowns).

### Suggested follow-ups for the desk
3–5 bullets: data to refresh, corporate actions to verify, alternative data checks.

End with exactly: *Research commentary only — not investment advice.*

Tone: institutional, concise. Cap ~900 words."""


def _trim_fundamentals(fa: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(fa, dict):
        return {}
    ratios = fa.get("ratios") if isinstance(fa.get("ratios"), dict) else {}
    keys = (
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
    head = {k: ratios.get(k) for k in keys if ratios.get(k) is not None}
    return {
        "stance": fa.get("stance"),
        "scores": fa.get("scores"),
        "headline_ratios": head or None,
    }


def _article_lines(layer: Dict[str, Any], limit: int = 40) -> List[Dict[str, Any]]:
    prev = layer.get("articles_preview")
    if not isinstance(prev, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in prev[:limit]:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "published": row.get("published"),
                "source": row.get("source"),
            }
        )
    return out


def build_equity_research_bundle(ctx: "EquityResearchRunContext") -> Dict[str, Any]:
    """Single JSON object for the desk model (no secrets)."""
    ta = ctx.results.get("technical_analysis")
    ta_compact = _compact_technical_for_llm(ta) if isinstance(ta, dict) else {}
    layer = ctx.results.get("news_tool_response")
    layer_d = layer if isinstance(layer, dict) else {}
    ns = ctx.results.get("news_sentiment")
    mlayer = ctx.results.get("market_tool_response")
    mlayer_d = mlayer if isinstance(mlayer, dict) else {}
    ms = ctx.results.get("market_sentiment")
    tc = ctx.results.get("trade_context")
    return {
        "symbol": ctx.symbol,
        "analysis_period_start": ctx.results.get("analysis_period_start"),
        "analysis_period_end": ctx.results.get("analysis_period_end"),
        "data_points": ctx.results.get("data_points"),
        "price_window_source": ctx.results.get("price_window_source"),
        "fundamental_analysis": _trim_fundamentals(ctx.results.get("fundamental_analysis") or {}),
        "technical_analysis": ta_compact,
        "news_sentiment": ns if isinstance(ns, dict) else {},
        "news_articles": _article_lines(layer_d, limit=45),
        "news_window": layer_d.get("window"),
        "market_sentiment": ms if isinstance(ms, dict) else {},
        "market_rationale": (mlayer_d.get("rationale_markdown") or "")[:4000]
        if isinstance(mlayer_d.get("rationale_markdown"), str)
        else "",
        "market_articles": _article_lines(mlayer_d, limit=35),
        "market_window": mlayer_d.get("window"),
        "trade_context": tc if isinstance(tc, dict) else {},
    }


def run_equity_desk_insight(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns ``{ "markdown": str, "model": str }`` or ``{ "skipped": True, "reason": str }`` /
    ``{ "error": str }``.
    """
    api_key = CONFIG.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("equity_desk.skip reason=no_openai_api_key")
        return {"skipped": True, "reason": "OPENAI_API_KEY is not set on the server."}

    model = CONFIG.get("OPENAI_EQUITY_DESK_MODEL") or config.OPENAI_TECH_VERDICT_MODEL
    logger.info("equity_desk.llm_request model=%s", model)
    user = (
        "Equity research bundle (JSON). Ground every statement in this object; cite gaps explicitly.\n\n"
        f"```json\n{json.dumps(bundle, indent=2, default=str)[:28000]}\n```"
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.35,
            max_tokens=2200,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            logger.warning("equity_desk.llm_empty_response model=%s", model)
            return {"error": "Empty model response."}
        return {"markdown": text, "model": model}
    except Exception as e:
        logger.warning("equity_desk.llm_request_failed model=%s err=%s", model, e, exc_info=True)
        return {"error": str(e)}
