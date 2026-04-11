"""
Fractal pivot support / resistance levels for chart overlays.

Research-style levels — not trade signals. Uses Bill-Williams-style fractals (2+2 bars).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def _fractal_pivot_highs(
    high: np.ndarray,
    left: int = 2,
    right: int = 2,
) -> List[Tuple[int, float]]:
    """Return (index, price) for bars that are the maximum of [i-left, i+right]."""
    out: List[Tuple[int, float]] = []
    n = len(high)
    for i in range(left, n - right):
        seg = high[i - left : i + right + 1]
        if high[i] >= np.nanmax(seg) and high[i] == np.max(seg):
            out.append((i, float(high[i])))
    return out


def _fractal_pivot_lows(
    low: np.ndarray,
    left: int = 2,
    right: int = 2,
) -> List[Tuple[int, float]]:
    out: List[Tuple[int, float]] = []
    n = len(low)
    for i in range(left, n - right):
        seg = low[i - left : i + right + 1]
        if low[i] <= np.nanmin(seg) and low[i] == np.min(seg):
            out.append((i, float(low[i])))
    return out


def _cluster_levels(
    levels: List[float],
    ref_price: float,
    tolerance_pct: float = 0.25,
    max_levels: int = 6,
) -> List[float]:
    """Merge levels within tolerance_pct of each other (vs ref for scale)."""
    if not levels:
        return []
    base = max(ref_price, 1e-9)
    levels = sorted(set(levels), reverse=True)
    merged: List[float] = []
    for p in levels:
        ok = True
        for m in merged:
            if abs(p - m) / base * 100.0 <= tolerance_pct:
                ok = False
                break
        if ok:
            merged.append(p)
        if len(merged) >= max_levels:
            break
    return merged


def compute_support_resistance_levels(
    df: pd.DataFrame,
    last_close: float,
    left: int = 2,
    right: int = 2,
    max_each: int = 6,
) -> Dict[str, Any]:
    """
    Build support (below last close) and resistance (above last close) from fractal pivots.

    Returns
    -------
    dict
        ``support`` / ``resistance`` lists of ``{price, label}`` plus ``method`` description.
    """
    if df is None or df.empty or "High" not in df.columns or "Low" not in df.columns:
        return {
            "support": [],
            "resistance": [],
            "method": "fractal_pivots(2,2); insufficient OHLC",
        }

    high = df["High"].astype(float).values
    low = df["Low"].astype(float).values

    ph = _fractal_pivot_highs(high, left=left, right=right)
    pl = _fractal_pivot_lows(low, left=left, right=right)

    # Prefer more recent pivots (later index) when clustering
    ph_sorted = sorted(ph, key=lambda x: x[0], reverse=True)
    pl_sorted = sorted(pl, key=lambda x: x[0], reverse=True)

    res_prices = [p for _, p in ph_sorted if p > last_close * 1.0001]
    sup_prices = [p for _, p in pl_sorted if p < last_close * 0.9999]

    res_levels = _cluster_levels(res_prices, last_close, max_levels=max_each)
    sup_levels = _cluster_levels(sup_prices, last_close, max_levels=max_each)
    # Nearest support below price first (highest level among supports)
    sup_levels = sorted(sup_levels, reverse=True)

    resistance = [{"price": round(p, 4), "label": f"R{i+1}"} for i, p in enumerate(res_levels)]
    support = [{"price": round(p, 4), "label": f"S{i+1}"} for i, p in enumerate(sup_levels)]

    return {
        "support": support,
        "resistance": resistance,
        "method": f"fractal_pivots(left={left},right={right}); clustered within 0.25% of last close",
    }
