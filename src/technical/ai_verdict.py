"""
LLM-assisted swing-trading workbook from technical snapshots: strategy matrix, levels, and a
beginner-oriented “how to use” section. Grounded in tool JSON; verify live prices.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple

from src.config.config import CONFIG, config

logger = logging.getLogger(__name__)


def _indicator_series_last(ind: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    tail: Dict[str, Any] = {}
    for key in keys:
        arr = ind.get(key)
        if isinstance(arr, list) and arr:
            last_v = next((x for x in reversed(arr) if x is not None), None)
            if last_v is not None:
                tail[f"{key}_last"] = last_v
    return tail


def _compact_technical_for_llm(technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Drop heavy OHLCV arrays; keep levels, last-bar indicator values, and summary fields."""
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
            tail = _indicator_series_last(
                ind,
                (
                    "rsi",
                    "macd",
                    "macd_signal",
                    "macd_histogram",
                    "ma_short",
                    "ma_long",
                    "bb_upper",
                    "bb_mid",
                    "bb_lower",
                    "stoch_k",
                    "stoch_d",
                    "volume",
                    "vwap",
                    "supertrend",
                    "keltner_upper",
                    "keltner_lower",
                    "adx",
                    "plus_di",
                    "minus_di",
                ),
            )
            ch["indicator_last"] = tail
        ta["chart"] = ch
    return ta


def _build_technical_verdict_task_preamble(api_result: Dict[str, Any], payload: Dict[str, Any]) -> str:
    """User-side task: trade context + data contract + next-session framing."""
    sym = str(api_result.get("symbol") or payload.get("symbol") or "").strip() or "(symbol)"
    ta = api_result.get("technical_analysis")
    last_bar = None
    if isinstance(ta, dict):
        ch = ta.get("chart")
        if isinstance(ch, dict):
            win = ch.get("window")
            if isinstance(win, dict):
                last_bar = win.get("last_bar")
    if not last_bar:
        last_bar = str(api_result.get("ohlc_index_end") or payload.get("ohlc_index_end") or "").strip() or None
    if last_bar:
        session_line = f"The latest session in the sample is **{last_bar}** (last close)."
    else:
        session_line = "Infer the last session from `ohlc_index_end` / chart `window` in the JSON."

    return (
        "**Operator request:** Build a **strategic swing-trading workbook** for NSE cash "
        f"**{sym}** using **only** the JSON below (includes advanced fields when present: ADX/DI, Supertrend, "
        "VWAP, Keltner/Bollinger squeeze, CMF/OBV, HV, vs-benchmark RS, pivot S/R, MAs, oscillators). "
        "You must **compare multiple named swing strategies** (see system prompt), map each to the data, "
        "and give **entry bands, profit targets, and stop losses** per strategy where applicable. "
        "**The reader may be new to trading:** also explain **in simple terms how each strategy is used correctly** "
        "(what to look for, common mistakes, when to stay out)—see the system prompt section on the beginner guide. "
        "Assume no live order book or off-payload catalysts unless in the JSON.\n\n"
        "**Deliverable:** Institutional Markdown: every level tied to payload fields; flag gaps or short history. "
        f"{session_line} "
        "Anchor tactical notes to the **next cash session** after that close when relevant.\n\n"
    )


def generate_technical_verdict(api_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns ``{ "text": str, "model": str }`` or ``{ "error": str }`` / skipped.
    """
    api_key = CONFIG.get("OPENAI_API_KEY")
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

    system = """You are the **swing-trading strategy desk** for **Indian NSE cash** equities. From one **daily** technical snapshot, produce a **structured comparison of swing approaches**—not a single opaque “call.” Be strategic: show **how different swing frameworks** would deploy capital, then converge on what the data best supports.

**Role & tone:** Institutional, risk-aware, explicit about **which indicators** justify each strategy. Do **not** claim employment at any firm or access to live order flow.

**Strategy toolkit (use a *subset* that the JSON can support—skip or mark “not applicable” if data missing):**
1. **Trend pullback swing** — dip to rising MA / shallow support in an ADX-supported trend; entry on hold/reclaim; stop under swing low.
2. **Breakout & retest** — horizontal or range break, optional retest of broken level; volume/CMF confirmation when visible.
3. **Bollinger / Keltner mean-reversion swing** — fade to midline when bands stretched *and* regime fits (e.g. ADX not extreme trend); tight stops outside band.
4. **Squeeze expansion** — `squeeze_on` or narrow BB width → plan for directional follow-through after expansion; entries on break of range with invalidation on false break.
5. **VWAP / anchor swing** — price vs anchored VWAP: trend-side pullbacks vs mean-reversion to VWAP; cite `anchored_vwap` and distance.
6. **Supertrend / directional band** — line as trailing stop reference; flip invalidates bias.
7. **Relative-strength swing** — use `vs_benchmark` when present: outperform vs underperform index for long/short bias overlay.
8. **Pivot / S&R swing** — entries and targets at named pivot supports/resistances; stops beyond next level.

**Professional requirements**
- **Ground every level** in `technical_analysis` (`last`, `last.advanced`, `labels`, `chart.support_resistance`, `chart.indicator_last`). Name the field when citing a number.
- Give **numeric** entry zones, **stop loss** prices, and **target(s)** per strategy row where possible.
- State **which strategies conflict** (e.g. trend vs mean-reversion) and **which the snapshot favors** using ADX, Supertrend direction, squeeze, RS.
- If history is thin, widen bands and say so.

**Beginner audience:** Assume the user may have **little or no trading experience**. You must still cite the JSON like a desk note, but add a dedicated section (below) that **teaches** how to use the strategies in real life—plain English, short sentences, no jargon without a one-line definition.

**Output contract:** Markdown with **EXACTLY** these section headings (order fixed):

## 1. Snapshot & data quality
Key figures, periods, and what is **not** in the payload.

## 2. Strategic market read (multi-lens)
Short paragraph: trend vs range vs transition using **ADX/DI**, **Supertrend**, **MA stack**, **squeeze**, **HV**, **CMF/OBV**—only as supported by JSON.

## 3. Swing strategy matrix
A **table** with columns: **Strategy** | **Valid when (from data)** | **Entry zone(s)** | **Stop loss** | **Target(s) / exit** | **Primary risk**. Include at least **4** distinct strategies from the toolkit above (mark N/A if impossible).

## 4. Support & resistance (unified map)
**S1… / R1…** with prices tied to pivots/MAs/bands.

## 5. Primary tactical plan
Pick **one** primary swing style (or “stand aside”) that best fits the snapshot; bullet **entry**, **stop**, **targets**, and **time/scenario invalidation**.

## 6. How to use these strategies (beginner guide)
This section is **mandatory** and should read like a patient tutor for someone **new to trading**. Include **all** of the following subsections (use these `###` subheadings):

### 6.1 Quick glossary
Define in **one line each** (for this note only): *support*, *resistance*, *stop-loss*, *target*, *swing trade*, *long* vs *short* (conceptually), and any indicator names you relied on (e.g. ADX, VWAP) if the beginner might not know them.

### 6.2 How each strategy works in practice
For **each** strategy you included in the matrix (or the top 4–5), write **3–6 short bullet points**: what you are actually betting on, **what you watch on the chart or in the numbers**, the **order of decisions** (e.g. “first check trend, then look for pullback”), and **when the setup is invalid** (walk away). Tie bullets back to fields in the JSON where possible.

### 6.3 Common beginner mistakes to avoid
4–6 bullets (e.g. trading without a stop, forcing a strategy when ADX says chop, ignoring gap/news risk, over-leveraging).

### 6.4 How to practice safely
3–5 bullets: paper/small size, one strategy at a time, journal trades, never risk money you cannot lose—**no personalized sizing in rupees**; keep it general and educational.

## 7. Executive line
One sentence summarizing the strategic bias and the lead setup.

**Length:** ~1000–1400 words. Prefer tables for the matrix."""

    preamble = _build_technical_verdict_task_preamble(api_result, payload)
    json_block = json.dumps(payload, indent=2, default=str)[:12000]
    user = (
        f"{preamble}"
        "**Data package (authoritative — cite from here):**\n"
        "```json\n"
        f"{json_block}\n"
        "```"
    )

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
            temperature=0.26,
            max_tokens=3200,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return {"error": "Empty model response."}
        return {"text": text, "model": model}
    except Exception as e:
        logger.warning("Technical verdict LLM failed: %s", e)
        return {"error": str(e)}
