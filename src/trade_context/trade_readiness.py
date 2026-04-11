"""
Trade *readiness* context: liquidity, volatility, cross-signal alignment, model fit.

Outputs support discretionary prep — not orders, targets, or regulated research.
Style: institutional desk checklist (risk-first). No buy/sell imperative.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# --- Scoring helpers (transparent, documented bands) ---


def _liquidity_score(volume: pd.Series) -> Tuple[float, Dict[str, Any]]:
    """0–100: recent volume vs 20d mean; penalize extreme thinness."""
    meta: Dict[str, Any] = {}
    if volume is None or len(volume) < 21:
        return 50.0, {"note": "insufficient volume history", "volume_ratio_recent_vs_20d": None}
    v = volume.astype(float).replace(0, np.nan).dropna()
    if len(v) < 21:
        return 50.0, {"note": "sparse volume", "volume_ratio_recent_vs_20d": None}
    ma20 = v.rolling(20, min_periods=10).mean().iloc[-1]
    recent5 = v.iloc[-5:].mean()
    ratio = float(recent5 / ma20) if ma20 and ma20 > 0 else 1.0
    meta["volume_ratio_recent_vs_20d"] = round(ratio, 3)
    # Adequate participation: ratio ~0.8–1.3 is fine; very low = illiquid tape
    if ratio < 0.35:
        score = 25.0
        meta["label"] = "thin vs 20d average — size carefully"
    elif ratio < 0.55:
        score = 45.0
        meta["label"] = "below recent participation"
    elif ratio <= 1.4:
        score = 72.0 + min(18.0, (ratio - 0.55) * 20.0)
        meta["label"] = "typical to active participation"
    else:
        score = 88.0
        meta["label"] = "elevated volume — confirm catalyst vs noise"
    return float(np.clip(score, 0.0, 100.0)), meta


def _volatility_execution_score(atr_pct: Optional[float], beta: Optional[float]) -> Tuple[float, Dict[str, Any]]:
    """
    0–100: favor moderate vol for controlled execution; penalize extreme ATR% and very high beta.
    """
    meta: Dict[str, Any] = {"atr_pct": atr_pct, "beta": beta}
    s = 70.0
    if atr_pct is not None and np.isfinite(atr_pct):
        # 1% ATR ~ easy; 5%+ ~ harsh for tight stops
        if atr_pct <= 0.015:
            s = 85.0
        elif atr_pct <= 0.03:
            s = 72.0
        elif atr_pct <= 0.045:
            s = 55.0
        else:
            s = 38.0
        meta["atr_band"] = "low" if atr_pct <= 0.02 else "moderate" if atr_pct <= 0.035 else "elevated"
    if beta is not None and np.isfinite(beta):
        abs_b = abs(float(beta))
        if abs_b > 1.35:
            s *= 0.88
            meta["beta_note"] = "|β| elevated vs market — book risk larger swings"
        elif abs_b < 0.45:
            meta["beta_note"] = "low β vs index — idiosyncratic drivers may dominate"
    return float(np.clip(s, 0.0, 100.0)), meta


def _alignment_score(
    rating: str,
    tech_stance: str,
    fund_stance: str,
    news_score: Optional[float],
) -> Tuple[float, Dict[str, Any]]:
    """Rough agreement across lenses → 0–100."""
    def sign_pead(r: str) -> int:
        u = (r or "").upper()
        if "STRONG BUY" in u or "BUY" in u.split():
            return 1
        if "STRONG SELL" in u or "SELL" in u.split():
            return -1
        return 0

    def sign_text(s: str) -> int:
        x = (s or "").lower()
        if any(w in x for w in ("bull", "constructive", "positive", "uptrend")):
            return 1
        if any(w in x for w in ("bear", "defensive", "negative", "down", "weak")):
            return -1
        return 0

    a1 = sign_pead(rating)
    a2 = sign_text(tech_stance)
    a3 = sign_text(fund_stance)
    a4 = 0
    if news_score is not None:
        a4 = 1 if news_score > 58 else (-1 if news_score < 42 else 0)
    votes = [a1, a2, a3, a4]
    non_zero = [v for v in votes if v != 0]
    if not non_zero:
        return 50.0, {"alignment": "mixed_or_neutral", "votes": votes}
    agree = len(set(non_zero)) == 1
    strength = len(non_zero)
    if agree:
        score = 55.0 + min(45.0, strength * 11.0)
        return float(score), {"alignment": "consistent", "votes": votes}
    return 38.0, {"alignment": "conflicting_signals", "votes": votes}


def _model_fit_score(r_squared: Optional[float]) -> float:
    if r_squared is None or not np.isfinite(r_squared):
        return 50.0
    r2 = float(r_squared)
    if r2 >= 0.18:
        return 78.0
    if r2 >= 0.10:
        return 62.0
    if r2 >= 0.06:
        return 48.0
    return 32.0


def compute_trade_context(results: Dict[str, Any], stock_data: pd.DataFrame) -> Dict[str, Any]:
    """
    Build execution-context block from a populated analyzer ``results`` and price ``stock_data``.

    Returns a dict stored as ``results['trade_context']`` and fed into synthesis.
    """
    vol_series = stock_data["Volume"] if stock_data is not None and "Volume" in stock_data.columns else None
    liq_score, liq_meta = _liquidity_score(vol_series if vol_series is not None else pd.Series(dtype=float))

    ta = results.get("technical_analysis") or {}
    last = ta.get("last") or {}
    atr_pct = last.get("atr_pct")
    if atr_pct is not None:
        atr_pct = float(atr_pct)
    mm = results.get("market_model") or {}
    beta = mm.get("beta")
    if beta is not None:
        beta = float(beta)

    vol_exec_score, vol_meta = _volatility_execution_score(atr_pct, beta)

    comp = results.get("composite_score") or {}
    rating = str(comp.get("rating") or "")
    fa = results.get("fundamental_analysis") or {}
    ns = results.get("news_sentiment") or {}
    news_total = ns.get("news_score_0_100") if isinstance(ns, dict) else None
    if news_total is not None:
        news_total = float(news_total)

    align_score, align_meta = _alignment_score(
        rating,
        str(ta.get("stance") or ""),
        str(fa.get("stance") or ""),
        news_total,
    )

    r2 = mm.get("r_squared") if mm else None
    if r2 is None and comp.get("data_quality"):
        r2 = (comp.get("data_quality") or {}).get("r_squared")
    fit_score = _model_fit_score(r2)

    # Weighted readiness (explicit — adjust in one place only)
    w_liq, w_vol, w_align, w_fit = 0.28, 0.24, 0.26, 0.22
    readiness = (
        w_liq * liq_score
        + w_vol * vol_exec_score
        + w_align * align_score
        + w_fit * fit_score
    )
    readiness = float(np.clip(readiness, 0.0, 100.0))

    flags: List[str] = []
    if liq_meta.get("label", "").startswith("thin"):
        flags.append("Liquidity: thin vs 20d volume — size and impact risk")
    if vol_meta.get("atr_band") == "elevated":
        flags.append("Volatility: wide ATR% — gap/stop placement matters")
    if r2 is not None and float(r2) < 0.08:
        flags.append("Model fit: low R² — event-study anchor is noisy")
    if beta is not None and abs(beta) > 1.35:
        flags.append("Beta: elevated vs NIFTY — book moves larger than index")

    return {
        "trade_readiness_score_0_100": readiness,
        "pillars": {
            "liquidity_execution": round(liq_score, 1),
            "volatility_regime": round(vol_exec_score, 1),
            "cross_signal_alignment": round(align_score, 1),
            "market_model_fit": round(fit_score, 1),
        },
        "liquidity_detail": liq_meta,
        "volatility_detail": vol_meta,
        "alignment_detail": align_meta,
        "risk_flags": flags,
        "weights_used": {"liquidity": w_liq, "volatility": w_vol, "alignment": w_align, "model_fit": w_fit},
        "disclaimer": (
            "Execution-context screen only — not investment advice, a suitability assessment, or an order."
        ),
    }
