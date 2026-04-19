"""
Fractal pivot support / resistance levels for chart overlays.

Research-style levels — not trade signals. Uses Bill-Williams-style fractals (2+2 bars).
Prominent levels: nearest clean zones to last close (readable chart), not full pivot ladders.
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


def _nearest_prominent_levels(
    merged_prices: List[float],
    last_close: float,
    *,
    above: bool,
    max_lines: int,
    min_separation_pct: float,
) -> List[float]:
    """
    From merged pivot prices on one side of ``last_close``, keep at most ``max_lines`` levels
    ordered by proximity to spot, enforcing a minimum % gap between drawn lines so the chart
    stays legible (desk-style: nearest active band, next meaningful step).
    """
    base = max(last_close, 1e-9)
    if above:
        side = sorted({p for p in merged_prices if p > last_close * 1.0001}, key=lambda p: p - last_close)
    else:
        side = sorted(
            {p for p in merged_prices if p < last_close * 0.9999},
            key=lambda p: last_close - p,
        )
    picked: List[float] = []
    for p in side:
        if all(abs(p - q) / base * 100.0 >= min_separation_pct for q in picked):
            picked.append(p)
        if len(picked) >= max_lines:
            break
    return picked


def compute_support_resistance_levels(
    df: pd.DataFrame,
    last_close: float,
    left: int = 2,
    right: int = 2,
    max_each: int = 2,
    cluster_pool_max: int = 14,
    cluster_tolerance_pct: float = 0.28,
    min_line_gap_pct: float = 0.45,
) -> Dict[str, Any]:
    """
    Build **prominent** support (below last close) and resistance (above) from fractal pivots.

    Pipeline: wide pivot pool → merge nearby prices → keep the **nearest** few levels per side
    with minimum %-separation so overlays stay readable (institutional snapshot, not a full ladder).
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

    ph_sorted = sorted(ph, key=lambda x: x[0], reverse=True)
    pl_sorted = sorted(pl, key=lambda x: x[0], reverse=True)

    res_prices = [p for _, p in ph_sorted if p > last_close * 1.0001]
    sup_prices = [p for _, p in pl_sorted if p < last_close * 0.9999]

    res_merged = _cluster_levels(
        res_prices,
        last_close,
        tolerance_pct=cluster_tolerance_pct,
        max_levels=cluster_pool_max,
    )
    sup_merged = _cluster_levels(
        sup_prices,
        last_close,
        tolerance_pct=cluster_tolerance_pct,
        max_levels=cluster_pool_max,
    )

    res_levels = _nearest_prominent_levels(
        res_merged,
        last_close,
        above=True,
        max_lines=max_each,
        min_separation_pct=min_line_gap_pct,
    )
    sup_levels = _nearest_prominent_levels(
        sup_merged,
        last_close,
        above=False,
        max_lines=max_each,
        min_separation_pct=min_line_gap_pct,
    )
    sup_levels = sorted(sup_levels, reverse=True)

    resistance = [{"price": round(p, 4), "label": f"R{i+1}"} for i, p in enumerate(res_levels)]
    support = [{"price": round(p, 4), "label": f"S{i+1}"} for i, p in enumerate(sup_levels)]

    return {
        "support": support,
        "resistance": resistance,
        "method": (
            f"fractal_pivots(left={left},right={right}); merged≈{cluster_tolerance_pct}% "
            f"then nearest {max_each}/side with ≥{min_line_gap_pct}% line gap (readable overlay)"
        ),
    }
