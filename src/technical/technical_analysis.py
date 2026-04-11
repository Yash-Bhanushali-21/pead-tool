"""
Post-event technical snapshot: RSI, MACD, moving averages, ATR%, volume vs average.

Uses only OHLCV in the analyzer window — for thin histories, periods shrink adaptively.
Not a prediction model; context for the next session alongside PEAD and fundamentals.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.technical.support_resistance import compute_support_resistance_levels

logger = logging.getLogger(__name__)

_CHART_MAX_BARS = 750


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta.clip(upper=0.0))
    avg_gain = gain.rolling(period, min_periods=max(2, period // 2)).mean()
    avg_loss = loss.rolling(period, min_periods=max(2, period // 2)).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev).abs(),
            (low - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=max(2, period // 2)).mean()


def _adaptive_periods(n: int) -> Dict[str, int]:
    """Shrink windows when history is short (e.g. newly listed names)."""
    rsi_p = min(14, max(5, n // 4))
    ma_s = min(20, max(5, n // 5))
    ma_l = min(50, max(10, n // 2))
    if ma_l >= n - 3:
        ma_l = max(10, n // 2)
    if ma_s >= ma_l:
        ma_s = max(5, ma_l // 2)
    return {"rsi": rsi_p, "ma_short": ma_s, "ma_long": ma_l, "atr": min(14, max(5, n // 4))}


class TechnicalAnalyzer:
    """Compute indicators and a 0–100 technical bias score."""

    def analyze(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp,
        symbol: str = "",
        *,
        include_chart_payload: bool = False,
    ) -> Dict[str, Any]:
        if stock_data is None or stock_data.empty or "Close" not in stock_data.columns:
            return self._empty_result("No price data")

        df = stock_data.sort_index().copy()
        close = df["Close"].astype(float)
        high = df["High"].astype(float) if "High" in df.columns else close
        low = df["Low"].astype(float) if "Low" in df.columns else close
        vol = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(index=df.index, dtype=float)

        n = len(df)
        p = _adaptive_periods(n)

        rsi = _rsi(close, p["rsi"])
        ma_s = close.rolling(p["ma_short"], min_periods=2).mean()
        ma_l = close.rolling(p["ma_long"], min_periods=2).mean()
        atr = _atr(high, low, close, p["atr"])
        atr_pct = (atr / close.replace(0, np.nan)).iloc[-1] if len(atr) else None

        ema12 = _ema(close, 12)
        ema26 = _ema(close, 26)
        macd_line = ema12 - ema26
        macd_signal = _ema(macd_line, 9)
        macd_hist = macd_line - macd_signal

        vol_ma = vol.rolling(20, min_periods=5).mean()
        vol_ratio = (vol.iloc[-1] / vol_ma.iloc[-1]) if vol_ma.iloc[-1] and vol_ma.iloc[-1] > 0 else None

        last = {
            "close": float(close.iloc[-1]),
            "rsi": float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None,
            "ma_short": float(ma_s.iloc[-1]) if pd.notna(ma_s.iloc[-1]) else None,
            "ma_long": float(ma_l.iloc[-1]) if pd.notna(ma_l.iloc[-1]) else None,
            "ma_short_period": p["ma_short"],
            "ma_long_period": p["ma_long"],
            "rsi_period": p["rsi"],
            "macd": float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None,
            "macd_signal": float(macd_signal.iloc[-1]) if pd.notna(macd_signal.iloc[-1]) else None,
            "macd_histogram": float(macd_hist.iloc[-1]) if pd.notna(macd_hist.iloc[-1]) else None,
            "atr_pct": float(atr_pct) if atr_pct is not None and np.isfinite(atr_pct) else None,
            "volume_vs_20d_avg": float(vol_ratio) if vol_ratio is not None and np.isfinite(vol_ratio) else None,
        }

        notes: List[str] = []
        if n < 30:
            notes.append(f"Short history ({n} sessions) — indicators use shortened lookbacks.")

        trend_score, trend_label = self._score_trend(last["close"], last["ma_short"], last["ma_long"])
        mom_score, mom_label = self._score_momentum(last["rsi"], last["macd_histogram"])
        vol_regime = self._volatility_label(last["atr_pct"])

        technical_score = float(np.clip(0.45 * trend_score + 0.40 * mom_score + 0.15 * self._volume_score(vol_ratio), 0, 100))
        stance = self._stance(technical_score, trend_label, mom_label, vol_regime)

        out: Dict[str, Any] = {
            "symbol": symbol,
            "last": last,
            "labels": {
                "trend": trend_label,
                "momentum": mom_label,
                "volatility": vol_regime,
            },
            "scores": {
                "trend": round(trend_score, 2),
                "momentum": round(mom_score, 2),
                "technical_score": round(technical_score, 2),
            },
            "stance": stance,
            "notes": notes,
            "sessions_in_sample": n,
        }

        if include_chart_payload:
            out["chart"] = self._build_chart_payload(
                df,
                close,
                rsi,
                ma_s,
                ma_l,
                macd_line,
                macd_signal,
                macd_hist,
                vol,
                p,
                float(close.iloc[-1]),
            )

        return out

    def _build_chart_payload(
        self,
        df: pd.DataFrame,
        close: pd.Series,
        rsi: pd.Series,
        ma_s: pd.Series,
        ma_l: pd.Series,
        macd_line: pd.Series,
        macd_signal: pd.Series,
        macd_hist: pd.Series,
        vol: pd.Series,
        periods: Dict[str, int],
        last_close: float,
    ) -> Dict[str, Any]:
        """OHLCV + aligned indicator series + pivot S/R for charting UIs."""
        plot_df = df.tail(_CHART_MAX_BARS).copy()
        idx = plot_df.index

        def _time_str(ts: Any) -> str:
            if hasattr(ts, "strftime"):
                return ts.strftime("%Y-%m-%d")
            return str(ts)[:10]

        bars: List[Dict[str, Any]] = []
        for t, row in plot_df.iterrows():
            o = float(row["Open"]) if "Open" in plot_df.columns else float(row["Close"])
            h = float(row["High"]) if "High" in plot_df.columns else float(row["Close"])
            lo = float(row["Low"]) if "Low" in plot_df.columns else float(row["Close"])
            c = float(row["Close"])
            v = float(row["Volume"]) if "Volume" in plot_df.columns else 0.0
            bars.append(
                {
                    "time": _time_str(t),
                    "open": round(o, 6),
                    "high": round(h, 6),
                    "low": round(lo, 6),
                    "close": round(c, 6),
                    "volume": round(v, 2),
                }
            )

        def _align(series: pd.Series) -> List[Optional[float]]:
            s = series.reindex(idx)
            out_list: List[Optional[float]] = []
            for v in s.values:
                if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                    out_list.append(None)
                else:
                    out_list.append(round(float(v), 6))
            return out_list

        sr = compute_support_resistance_levels(plot_df, last_close=last_close)

        return {
            "bars": bars,
            "indicators": {
                "ma_short": _align(ma_s),
                "ma_long": _align(ma_l),
                "rsi": _align(rsi),
                "macd": _align(macd_line),
                "macd_signal": _align(macd_signal),
                "macd_histogram": _align(macd_hist),
                "volume": _align(vol),
            },
            "periods": {
                "ma_short": periods["ma_short"],
                "ma_long": periods["ma_long"],
                "rsi": periods["rsi"],
            },
            "support_resistance": sr,
        }

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "symbol": "",
            "last": {},
            "labels": {"trend": "n/a", "momentum": "n/a", "volatility": "n/a"},
            "scores": {"trend": 0, "momentum": 0, "technical_score": 0},
            "stance": f"Unavailable ({reason})",
            "notes": [reason],
            "sessions_in_sample": 0,
        }

    @staticmethod
    def _score_trend(
        close: Optional[float],
        ma_s: Optional[float],
        ma_l: Optional[float],
    ) -> Tuple[float, str]:
        if close is None or ma_s is None or ma_l is None:
            return 50.0, "insufficient MA data"
        if close > ma_s > ma_l:
            return 78.0, "price above short & long MA (bullish stack)"
        if close > ma_s:
            return 62.0, "price above short MA"
        if close < ma_s < ma_l:
            return 22.0, "price below short & long MA (bearish stack)"
        if close < ma_s:
            return 38.0, "price below short MA"
        return 50.0, "mixed MA structure"

    @staticmethod
    def _score_momentum(
        rsi: Optional[float],
        macd_hist: Optional[float],
    ) -> Tuple[float, str]:
        score = 50.0
        parts = []
        if rsi is not None:
            if rsi >= 70:
                score -= 8.0
                parts.append(f"RSI {rsi:.1f} (overbought zone)")
            elif rsi <= 30:
                score += 5.0
                parts.append(f"RSI {rsi:.1f} (oversold bounce risk)")
            elif rsi >= 55:
                score += 12.0
                parts.append(f"RSI {rsi:.1f} (firm)")
            elif rsi <= 45:
                score -= 10.0
                parts.append(f"RSI {rsi:.1f} (weak)")
            else:
                parts.append(f"RSI {rsi:.1f} (neutral)")
        if macd_hist is not None:
            if macd_hist > 0:
                score += 10.0
                parts.append("MACD histogram > 0")
            else:
                score -= 8.0
                parts.append("MACD histogram < 0")
        score = float(np.clip(score, 0, 100))
        label = "; ".join(parts) if parts else "no momentum inputs"
        return score, label

    @staticmethod
    def _volume_score(vol_ratio: Optional[float]) -> float:
        if vol_ratio is None or not np.isfinite(vol_ratio):
            return 50.0
        if vol_ratio > 1.5:
            return 65.0
        if vol_ratio < 0.7:
            return 42.0
        return 52.0

    @staticmethod
    def _volatility_label(atr_pct: Optional[float]) -> str:
        if atr_pct is None:
            return "unknown"
        if atr_pct > 0.04:
            return "high intraday volatility (ATR% elevated)"
        if atr_pct > 0.025:
            return "moderate volatility"
        return "relatively calm vs recent range"

    @staticmethod
    def _stance(
        tech_score: float,
        trend_l: str,
        mom_l: str,
        vol_l: str,
    ) -> str:
        if tech_score >= 62:
            base = "Technical posture skews constructive vs recent structure."
        elif tech_score <= 38:
            base = "Technical posture skews defensive vs recent structure."
        else:
            base = "Technical posture is mixed — no clean trend edge."
        return f"{base} Trend: {trend_l}. Volatility: {vol_l}."
