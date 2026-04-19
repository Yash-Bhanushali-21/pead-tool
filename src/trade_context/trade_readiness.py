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


def _liquidity_score(volume: pd.Series) -> Tuple[Optional[float], Dict[str, Any]]:
    """0–100: recent volume vs 20d mean; penalize extreme thinness. None if data insufficient."""
    meta: Dict[str, Any] = {}
    if volume is None or len(volume) < 21:
        return None, {"reason": "insufficient_volume_history", "volume_ratio_recent_vs_20d": None}
    v = volume.astype(float).replace(0, np.nan).dropna()
    if len(v) < 21:
        return None, {"reason": "sparse_volume", "volume_ratio_recent_vs_20d": None}
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


def _volatility_execution_score(atr_pct: Optional[float], beta: Optional[float]) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    0–100: favor moderate vol for controlled execution; penalize extreme ATR% and very high beta.
    None if ATR% is unavailable (no synthetic neutral).
    """
    meta: Dict[str, Any] = {"atr_pct": atr_pct, "beta": beta}
    if atr_pct is None or not np.isfinite(atr_pct):
        meta["reason"] = "atr_pct_unavailable"
        return None, meta
    s = 70.0
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
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Rough agreement across lenses → 0–100, or None if inputs are too thin to score honestly.

    Requires at least two non-neutral directional votes (from PEAD rating, technical stance,
    fundamentals stance, or news score bands).
    """
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
    if news_score is not None and np.isfinite(float(news_score)):
        ns = float(news_score)
        a4 = 1 if ns > 58 else (-1 if ns < 42 else 0)
    votes = [a1, a2, a3, a4]
    non_zero = [v for v in votes if v != 0]
    if len(non_zero) < 2:
        return None, {
            "alignment": "insufficient_inputs",
            "votes": votes,
            "reason": "need_at_least_two_directional_signals_across_lenses",
        }
    agree = len(set(non_zero)) == 1
    strength = len(non_zero)
    if agree:
        score = 55.0 + min(45.0, strength * 11.0)
        return float(score), {"alignment": "consistent", "votes": votes}
    return 38.0, {"alignment": "conflicting_signals", "votes": votes}


def _model_fit_score(r_squared: Optional[float]) -> Optional[float]:
    if r_squared is None or not np.isfinite(r_squared):
        return None
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

    Missing inputs produce ``null`` pillar scores (no neutral synthetic fill). The headline
    ``trade_readiness_score_0_100`` is ``null`` unless **all** four pillars are computable.
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
    if news_total is not None and not (isinstance(news_total, float) and np.isnan(news_total)):
        try:
            news_total = float(news_total)
        except (TypeError, ValueError):
            news_total = None

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

    w_liq, w_vol, w_align, w_fit = 0.28, 0.24, 0.26, 0.22
    pillar_values = [liq_score, vol_exec_score, align_score, fit_score]
    readiness: Optional[float]
    if any(p is None for p in pillar_values):
        readiness = None
        missing_pillars = [
            name
            for name, p in zip(
                ("liquidity_execution", "volatility_regime", "cross_signal_alignment", "market_model_fit"),
                pillar_values,
            )
            if p is None
        ]
    else:
        readiness = float(
            np.clip(
                w_liq * float(liq_score)
                + w_vol * float(vol_exec_score)
                + w_align * float(align_score)
                + w_fit * float(fit_score),
                0.0,
                100.0,
            )
        )
        missing_pillars = []

    flags: List[str] = []
    if liq_meta.get("label", "").startswith("thin"):
        flags.append("Liquidity: thin vs 20d volume — size and impact risk")
    if vol_meta.get("atr_band") == "elevated":
        flags.append("Volatility: wide ATR% — gap/stop placement matters")
    if r2 is not None and float(r2) < 0.08:
        flags.append("Model fit: low R² — event-study anchor is noisy")
    if beta is not None and abs(beta) > 1.35:
        flags.append("Beta: elevated vs NIFTY — book moves larger than index")

    def _p(v: Optional[float]) -> Optional[float]:
        return None if v is None else round(float(v), 1)

    out: Dict[str, Any] = {
        "trade_readiness_score_0_100": readiness,
        "readiness_complete": readiness is not None,
        "missing_pillars": missing_pillars,
        "pillars": {
            "liquidity_execution": _p(liq_score),
            "volatility_regime": _p(vol_exec_score),
            "cross_signal_alignment": _p(align_score),
            "market_model_fit": _p(fit_score),
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
    return out
