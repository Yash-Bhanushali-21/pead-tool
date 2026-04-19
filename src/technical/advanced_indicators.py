"""
Advanced OHLCV-derived indicators: regime (ADX/DI), flow (OBV, CMF), VWAP, volatility (HV, BBW),
Keltner + squeeze, Supertrend-style band, relative strength vs benchmark.

All series align to the input index; thin histories use shorter min_periods where noted.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _ema_wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder / RMA smoothing: alpha = 1/period."""
    return series.ewm(alpha=1.0 / float(period), min_periods=period, adjust=False).mean()


def adx_di(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Returns (adx, plus_di, minus_di, dx) all 0-100 scale for DI/ADX where applicable.
    """
    h = high.astype(float)
    lo = low.astype(float)
    c = close.astype(float)
    prev_h = h.shift(1)
    prev_lo = lo.shift(1)
    prev_c = c.shift(1)

    tr = pd.concat([h - lo, (h - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)

    up_move = h - prev_h
    down_move = prev_lo - lo
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=h.index)
    minus_dm = pd.Series(minus_dm, index=h.index)

    tr_s = _ema_wilder(tr, period)
    plus_dm_s = _ema_wilder(plus_dm, period)
    minus_dm_s = _ema_wilder(minus_dm, period)

    plus_di = 100.0 * plus_dm_s / tr_s.replace(0, np.nan)
    minus_di = 100.0 * minus_dm_s / tr_s.replace(0, np.nan)
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    adx = _ema_wilder(dx, period)
    return adx, plus_di, minus_di, dx


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[pd.Series, pd.Series]:
    """
    Simplified Supertrend (common OHLC implementation): band flip on prior upper/lower breach.
    Returns (supertrend_line, direction) with direction +1 = bullish (line tracks lower band).
    """
    hl2 = (high.astype(float) + low.astype(float)) / 2.0
    prev_close = close.astype(float).shift(1)
    tr = pd.concat(
        [
            high.astype(float) - low.astype(float),
            (high.astype(float) - prev_close).abs(),
            (low.astype(float) - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period, min_periods=max(2, period // 2)).mean()
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    n = len(close)
    in_uptrend = np.ones(n, dtype=bool)
    c = close.astype(float).values
    u = upper.values
    l = lower.values
    for i in range(1, n):
        if c[i] > u[i - 1]:
            in_uptrend[i] = True
        elif c[i] < l[i - 1]:
            in_uptrend[i] = False
        else:
            in_uptrend[i] = in_uptrend[i - 1]

    st_vals = np.where(in_uptrend, l, u)
    direction = np.where(in_uptrend, 1, -1)
    return (
        pd.Series(st_vals, index=close.index),
        pd.Series(direction, index=close.index),
    )


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-balance volume."""
    c = close.astype(float)
    v = volume.astype(float).clip(lower=0.0)
    direction = np.sign(c.diff().fillna(0.0))
    return (direction * v).cumsum()


def chaikin_money_flow(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Chaikin Money Flow: sum(MFV) / sum(V) over window."""
    h = high.astype(float)
    lo = low.astype(float)
    c = close.astype(float)
    v = volume.astype(float).clip(lower=0.0)
    hl = (h - lo).replace(0, np.nan)
    mfm = ((c - lo) - (h - c)) / hl
    mfm = mfm.fillna(0.0)
    mfv = mfm * v
    min_p = max(3, period // 2)
    return mfv.rolling(period, min_periods=min_p).sum() / v.rolling(period, min_periods=min_p).sum()


def anchored_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """Session-anchored VWAP from the first bar of the series (analysis window)."""
    h = high.astype(float)
    lo = low.astype(float)
    c = close.astype(float)
    v = volume.astype(float).clip(lower=0.0)
    tp = (h + lo + c) / 3.0
    pv = tp * v
    cum_v = v.cumsum().replace(0, np.nan)
    return pv.cumsum() / cum_v


def historical_volatility_annualized(close: pd.Series, period: int = 20) -> pd.Series:
    """Log-return realized vol, annualized (sqrt(252))."""
    c = close.astype(float)
    lr = np.log(c / c.shift(1))
    min_p = max(5, period // 2)
    return lr.rolling(period, min_periods=min_p).std() * np.sqrt(252.0)


def bollinger_bandwidth_pct(mid: pd.Series, upper: pd.Series, lower: pd.Series) -> pd.Series:
    """(Upper - Lower) / Mid as percentage; Mid near zero guarded."""
    m = mid.replace(0, np.nan)
    return 100.0 * (upper - lower) / m


def keltner_channels(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    ema_period: int = 20,
    atr_period: int = 10,
    atr_mult: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Keltner: EMA mid ± atr_mult * ATR(high,low,close)."""
    c = close.astype(float)
    h = high.astype(float)
    lo = low.astype(float)
    prev_c = c.shift(1)
    tr = pd.concat([h - lo, (h - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_period, min_periods=max(2, atr_period // 2)).mean()
    min_e = max(3, ema_period // 2)
    mid = c.ewm(span=ema_period, min_periods=min_e, adjust=False).mean()
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr
    return upper, mid, lower


def squeeze_bb_inside_kc(
    bb_upper: pd.Series,
    bb_lower: pd.Series,
    kc_upper: pd.Series,
    kc_lower: pd.Series,
) -> pd.Series:
    """True when Bollinger bandwidth is inside Keltner (classic 'squeeze' setup)."""
    bb_w = (bb_upper - bb_lower).abs()
    kc_w = (kc_upper - kc_lower).abs()
    return (bb_w < kc_w) & bb_w.notna() & kc_w.notna()


def relative_strength_vs_benchmark(
    stock_close: pd.Series,
    bench_close: pd.Series,
    lookback: int = 20,
) -> Dict[str, Any]:
    """
    Ratio (stock/bench)*100 and % change of ratio over lookback sessions.
    bench_close must be aligned to stock_close index.
    """
    s = stock_close.astype(float)
    b = bench_close.astype(float).reindex(s.index).ffill().bfill()
    ratio = (s / b.replace(0, np.nan)) * 100.0
    r0 = ratio.shift(lookback)
    rs_change_pct = np.where(r0.notna() & (r0 != 0), (ratio / r0 - 1.0) * 100.0, np.nan)
    return {
        "rs_ratio_x100": ratio,
        "rs_ratio_change_pct_vs_bench": pd.Series(rs_change_pct, index=s.index),
    }


def swing_extreme_last_bar(high: pd.Series, low: pd.Series, window: int = 5) -> Dict[str, bool]:
    """Last bar is highest high / lowest low of the last `window` sessions (local swing proxy)."""
    if len(high) < window:
        return {"local_high_last": False, "local_low_last": False}
    h = high.astype(float).iloc[-window:]
    lo = low.astype(float).iloc[-window:]
    last_hi = float(high.astype(float).iloc[-1])
    last_lo = float(low.astype(float).iloc[-1])
    return {
        "local_high_last": bool(last_hi >= float(h.max())),
        "local_low_last": bool(last_lo <= float(lo.min())),
    }


def adx_regime_label(adx_last: Optional[float]) -> str:
    if adx_last is None or not np.isfinite(adx_last):
        return "ADX n/a"
    if adx_last >= 25:
        return f"trending regime (ADX {adx_last:.1f})"
    if adx_last >= 20:
        return f"transition / moderate trend (ADX {adx_last:.1f})"
    return f"range / weak trend (ADX {adx_last:.1f})"
