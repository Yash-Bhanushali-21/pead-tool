"""
LLM-assisted *research commentary* on technical snapshots — not investment advice.

Output is educational desk-style framing (entry/exit *discussion*, risks). No client
recommendation language; no firm affiliation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from src.config.settings import config

logger = logging.getLogger(__name__)


def _compact_technical_for_llm(technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Drop heavy OHLCV arrays; keep levels and summary fields."""
    ta = json.loads(json.dumps(technical_analysis, default=str))
    ch = ta.get("chart")
    if isinstance(ch, dict):
        bars = ch.get("bars")
        n = len(bars) if isinstance(bars, list) else 0
        ind = ch.get("indicators") or {}
        ch = {
            k: v
            for k, v in ch.items()
            if k not in ("bars", "indicators")
        }
        ch["bars_in_view"] = n
        if isinstance(ind, dict):
            tail: Dict[str, Any] = {}
            for key in ("rsi", "macd", "macd_histogram"):
                arr = ind.get(key)
                if isinstance(arr, list) and arr:
                    last_v = next((x for x in reversed(arr) if x is not None), None)
                    tail[f"{key}_last"] = last_v
            ch["indicator_last"] = tail
        ta["chart"] = ch
    return ta


def generate_technical_verdict(api_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns ``{ "text": str, "model": str }`` or ``{ "error": str }`` / skipped.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "skipped": True,
            "reason": "OPENAI_API_KEY is not set on the server.",
        }

    ta = api_result.get("technical_analysis")
    if not isinstance(ta, dict):
        return {"error": "No technical_analysis in payload."}

    compact_ta = _compact_technical_for_llm(ta)
    payload = {
        "symbol": api_result.get("symbol"),
        "price_window": api_result.get("price_window"),
        "announcement_date_used": api_result.get("announcement_date_used"),
        "range_start": api_result.get("range_start"),
        "range_end": api_result.get("range_end"),
        "ohlc_index_start": api_result.get("ohlc_index_start"),
        "ohlc_index_end": api_result.get("ohlc_index_end"),
        "technical_analysis": compact_ta,
    }

    system = """You are a senior equities *research* analyst drafting an internal EDUCATIONAL note (Indian NSE cash equities). This is NOT investment advice, NOT a solicitation, and you do NOT speak for or represent any asset manager (do not name Blackstone, BlackRock, JPM, or any firm).

The user tool outputs indicators and heuristic pivot support/resistance only — fundamentals, liquidity, news, and corporate events may dominate real outcomes.

Write in clear Markdown with EXACTLY these sections and headings:

## Structure read
2–4 sentences on trend/momentum/volatility vs MAs and pivots.

## Hypothetical entry framework (conditional)
Bullet points: what would need to be true for a *discussion* of long vs short vs flat bias; reference nearest support/resistance as *zones*, not guarantees. No “buy now”.

## Risk & invalidation
Bullets: stop / time-stop / scenario that voids the technical read (e.g. close below key zone, regime change).

## Exit & position-management ideas
Bullets: scaling, trailing vs fixed targets using levels as *reference bands* only.

## One-line verdict
A single nuanced sentence — balanced, no imperative to trade.

End with a line: *Research commentary only — not investment advice.*

Tone: institutional desk, risk-first, concise. Max ~650 words."""

    user = f"Context JSON (technical snapshot):\n```json\n{json.dumps(payload, indent=2, default=str)[:12000]}\n```"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = config.OPENAI_TECH_VERDICT_MODEL
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.35,
            max_tokens=1400,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return {"error": "Empty model response."}
        return {"text": text, "model": model}
    except Exception as e:
        logger.warning("Technical verdict LLM failed: %s", e)
        return {"error": str(e)}
