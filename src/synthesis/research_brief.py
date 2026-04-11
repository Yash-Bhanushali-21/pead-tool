"""
Desk-style research brief: blends PEAD, fundamentals, and technicals into one narrative.

Outputs are for personal research workflows — not regulated investment advice.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _next_session_note() -> str:
    now = datetime.now()
    # Next Indian equity session (Mon–Fri); rough note only
    wd = now.weekday()
    if wd == 4:  # Friday
        return "Next primary cash session is typically Monday (subject to exchange holiday calendar)."
    if wd == 5:  # Saturday
        return "Weekend — next primary session is typically Monday; overnight/global gaps can affect the open."
    if wd == 6:
        return "Sunday — next primary session is typically Monday; gap risk at open vs last close."
    return "For same-week sessions, watch opening gap vs prior close and liquidity at the open."


def _blend_scores(
    composite: float,
    fund_score: Optional[float],
    tech_score: Optional[float],
    news_score: Optional[float],
    confidence: float,
    r_squared: Optional[float],
    trade_readiness: Optional[float] = None,
) -> Tuple[float, str]:
    """
    Transparent weighted blend in [-1, 1] mapped from pillar scores centered at 50.

    Optional **trade_readiness** (0–100) adds an execution-context pillar: liquidity,
    volatility regime, cross-signal alignment, and market-model fit — not a trade signal.
    """
    pead_n = (composite - 50.0) / 50.0
    f_n = (fund_score - 50.0) / 50.0 if fund_score is not None else 0.0
    t_n = (tech_score - 50.0) / 50.0 if tech_score is not None else 0.0
    n_n = (news_score - 50.0) / 50.0 if news_score is not None else 0.0
    tr_n = (trade_readiness - 50.0) / 50.0 if trade_readiness is not None else 0.0

    if news_score is not None and trade_readiness is not None:
        w_pead, w_f, w_t, w_n, w_tr = 0.20, 0.16, 0.14, 0.20, 0.30
        blend = (
            w_pead * pead_n
            + w_f * f_n
            + w_t * t_n
            + w_n * n_n
            + w_tr * tr_n
        )
    elif trade_readiness is not None:
        w_pead, w_f, w_t, w_tr = 0.30, 0.22, 0.20, 0.28
        blend = w_pead * pead_n + w_f * f_n + w_t * t_n + w_tr * tr_n
    elif news_score is not None:
        w_pead, w_f, w_t, w_n = 0.28, 0.22, 0.20, 0.30
        blend = w_pead * pead_n + w_f * f_n + w_t * t_n + w_n * n_n
    else:
        w_pead, w_f, w_t = 0.38, 0.32, 0.30
        blend = w_pead * pead_n + w_f * f_n + w_t * t_n

    if r_squared is not None and np.isfinite(r_squared) and r_squared < 0.08:
        blend *= 0.82
    if confidence < 0.55:
        blend *= 0.88

    blend = float(np.clip(blend, -1.0, 1.0))

    if blend >= 0.22:
        bias = "CONSTRUCTIVE (research bias — not a buy call)"
    elif blend >= 0.06:
        bias = "NEUTRAL-LEAN-POSITIVE"
    elif blend <= -0.22:
        bias = "DEFENSIVE / AVOID NEW RISK"
    elif blend <= -0.06:
        bias = "NEUTRAL-LEAN-NEGATIVE"
    else:
        bias = "NEUTRAL — no edge from this stack alone"

    return blend, bias


def _trade_template(blend: float, atr_high: bool, pead_rating: str) -> str:
    """Operational template language — not an order."""
    if blend <= -0.15 or "SELL" in (pead_rating or "").upper():
        return "Template: no new long initiation; consider risk reduction or hedges vs existing exposure (if any)."
    if blend >= 0.18 and not atr_high:
        return "Template: optional tactical participation only — small size, predefined stop, liquidity checks."
    if blend >= 0.18 and atr_high:
        return "Template: if participating, favor smaller size and wider risk limits — ATR suggests volatile tape."
    if abs(blend) < 0.12:
        return "Template: watchlist / no action from this model alone; wait for confirmation or new information."
    return "Template: discretionary — align with your risk limits and broader book."


def build_research_brief_payload(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build structured synthesis + narrative text from a completed analyze_announcement result.
    """
    sym = results.get("symbol", "")
    ann = results.get("announcement_date")
    comp = results.get("composite_score") or {}
    fa = results.get("fundamental_analysis") or {}
    ta = results.get("technical_analysis") or {}
    ns = results.get("news_sentiment") or {}

    composite_score = float(comp.get("composite_score") or 0)
    rating = comp.get("rating") or "N/A"
    conf = float(comp.get("confidence") or 0)

    f_scores = fa.get("scores") or {}
    fund_total = f_scores.get("fundamental_score")

    t_scores = ta.get("scores") or {}
    tech_total = t_scores.get("technical_score")

    news_total = ns.get("news_score_0_100")
    if news_total is not None:
        news_total = float(news_total)

    tc = results.get("trade_context") or {}
    trade_ready = tc.get("trade_readiness_score_0_100")
    if trade_ready is not None:
        try:
            trade_ready = float(trade_ready)
        except (TypeError, ValueError):
            trade_ready = None

    dq = comp.get("data_quality") or {}
    r2 = dq.get("r_squared")

    mm = results.get("market_model") or {}
    r_squared = mm.get("r_squared") if mm else r2

    car_data = results.get("car_data") or {}
    car_30 = None
    if 30 in car_data:
        car_30 = car_data[30].get("car")

    blend, bias = _blend_scores(
        composite_score,
        fund_total,
        tech_total,
        news_total,
        conf,
        r_squared,
        trade_readiness=trade_ready,
    )

    atr_pct = (ta.get("last") or {}).get("atr_pct")
    atr_high = atr_pct is not None and atr_pct > 0.035
    template = _trade_template(blend, atr_high, rating)

    lines: List[str] = []
    lines.append("")
    lines.append("=" * 76)
    lines.append("RESEARCH BRIEF — UNIFIED VIEW (PEAD + FUNDAMENTALS + TECH + NEWS + EXECUTION)")
    lines.append("=" * 76)
    lines.append("Not investment advice. One input among many — you own execution and risk.")
    lines.append("")
    lines.append(f"Symbol: {sym}  |  Event date (study anchor): {ann}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {_next_session_note()}")
    lines.append("")

    lines.append("— PEAD (event / drift lens) —")
    lines.append(f"  Composite: {composite_score:.2f}/100  |  Rating: {rating}  |  Confidence: {conf:.0%}")
    if car_30 is not None:
        lines.append(f"  CAR [30d] (abnormal drift vs market model): {car_30 * 100:.2f}% (decimal {car_30:.4f})")
    lines.append(f"  Model R²: {r_squared if r_squared is not None else 'n/a'}")
    lines.append("")

    lines.append("— Fundamentals (slow lens, Yahoo) —")
    lines.append(f"  Score: {fund_total if fund_total is not None else 'n/a'}/100")
    lines.append(f"  Stance: {fa.get('stance', 'n/a')}")
    lines.append("")

    lines.append("— Technical (price structure, same sample window) —")
    last = ta.get("last") or {}
    lines.append(f"  Score: {tech_total if tech_total is not None else 'n/a'}/100")
    lines.append(f"  RSI({last.get('rsi_period', '?')}): {last.get('rsi', 'n/a')}")
    lines.append(
        f"  MACD hist: {last.get('macd_histogram', 'n/a')}  |  "
        f"ATR%: {last.get('atr_pct', 'n/a')}"
    )
    lines.append(f"  {ta.get('stance', '')}")
    if ta.get("notes"):
        for n in ta["notes"]:
            lines.append(f"  Note: {n}")
    lines.append("")

    lines.append("— News & media (headlines / snippets; not exhaustive) —")
    lines.append(
        f"  Articles sampled: {ns.get('article_count', 0)}  |  "
        f"Method: {ns.get('method', 'n/a')}"
    )
    if news_total is not None:
        lines.append(f"  News sentiment score (0–100): {news_total:.1f}")
    if ns.get("mean_polarity") is not None:
        lines.append(
            f"  TextBlob mean polarity: {ns.get('mean_polarity'):.3f} "
            f"(−1 bearish … +1 bullish)"
        )
    llm = ns.get("llm")
    if llm:
        lines.append(f"  LLM overall: {llm.get('overall', 'n/a')} "
                     f"(confidence {llm.get('confidence', 'n/a')})")
        if llm.get("one_line"):
            lines.append(f"  LLM one-liner: {llm['one_line']}")
        if llm.get("themes"):
            lines.append(f"  Themes: {', '.join(llm['themes'][:5])}")
    elif not ns.get("article_count"):
        lines.append("  No articles retrieved — check network or query coverage.")
    elif not ns.get("openai_used"):
        lines.append(
            "  LLM layer skipped (set OPENAI_API_KEY for narrative synthesis)."
        )
    lines.append("")

    lines.append("— Trade readiness (execution context — not a recommendation) —")
    if tc.get("error"):
        lines.append(f"  Unavailable: {tc.get('error')}")
    elif trade_ready is not None:
        lines.append(f"  Composite readiness (0–100): {trade_ready:.1f}")
        pl = tc.get("pillars") or {}
        lines.append(
            f"  Pillars — liquidity: {pl.get('liquidity_execution', 'n/a')}, "
            f"vol regime: {pl.get('volatility_regime', 'n/a')}, "
            f"alignment: {pl.get('cross_signal_alignment', 'n/a')}, "
            f"model fit: {pl.get('market_model_fit', 'n/a')}"
        )
        for fl in tc.get("risk_flags") or []:
            lines.append(f"  Flag: {fl}")
        lines.append(f"  {tc.get('disclaimer', '')}")
    else:
        lines.append("  Not computed for this run.")
    lines.append("")

    lines.append("— Synthesis (rule-based blend) —")
    lines.append(
        f"  Blended bias score (internal): {blend:+.3f}  (range -1 … +1)"
        + (
            "  |  includes execution-readiness pillar when present"
            if trade_ready is not None
            else ""
        )
    )
    lines.append(f"  Analyst-style bias label: {bias}")
    lines.append(f"  {template}")
    lines.append("")
    lines.append("— How to use before the next session —")
    lines.append("  • Align this brief with liquidity, position limits, and news since the model run.")
    lines.append("  • If PEAD confidence is low or R² is tiny, overweight discretion vs the numeric score.")
    lines.append("  • Technicals here are descriptive on the sample window — not a standalone alpha model.")
    lines.append("  • News scan uses public RSS/Yahoo snippets — not full paywalled text; tone can lag price.")
    lines.append("=" * 76)
    lines.append("")
    text = "\n".join(lines)
    out: Dict[str, Any] = {
        "text": text,
        "blend_score": blend,
        "bias_label": bias,
        "trade_template": template,
        "pead_composite": composite_score,
        "fundamental_score": fund_total,
        "technical_score": tech_total,
        "news_score": news_total,
        "trade_readiness_score": trade_ready,
        "trade_context": tc if tc else None,
    }
    return out


def generate_research_brief(results: Dict[str, Any]) -> str:
    """Backward-compatible: return narrative only."""
    return build_research_brief_payload(results)["text"]
