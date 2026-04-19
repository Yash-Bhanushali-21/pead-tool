"""
Post-event technical snapshot: RSI, MACD, MAs, ATR%, volume, plus advanced desk indicators
(ADX/DI, Supertrend, OBV, CMF, anchored VWAP, BB width, Keltner + squeeze, HV, vs benchmark).

Uses only OHLCV in the analyzer window — for thin histories, periods shrink adaptively.
Not a prediction model; context for the next session alongside PEAD and fundamentals.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.technical.advanced_indicators import (
    adx_di,
    adx_regime_label,
    anchored_vwap,
    bollinger_bandwidth_pct,
    chaikin_money_flow,
    historical_volatility_annualized,
    keltner_channels,
    obv,
    relative_strength_vs_benchmark,
    squeeze_bb_inside_kc,
    supertrend,
    swing_extreme_last_bar,
)
from src.technical.support_resistance import compute_support_resistance_levels

logger = logging.getLogger(__name__)

_CHART_HARD_CAP = 4000  # safety only; equity windows are usually << this


def _bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period, min_periods=max(5, period // 4)).mean()
    std = close.rolling(period, min_periods=max(5, period // 4)).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def _stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, smooth_k: int = 3, smooth_d: int = 3
) -> tuple[pd.Series, pd.Series]:
    ll = low.rolling(k_period, min_periods=max(5, k_period // 2)).min()
    hh = high.rolling(k_period, min_periods=max(5, k_period // 2)).max()
    denom = (hh - ll).replace(0, np.nan)
    raw_k = 100.0 * (close - ll) / denom
    k = raw_k.rolling(smooth_k, min_periods=1).mean()
    d = k.rolling(smooth_d, min_periods=1).mean()
    return k, d


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
        benchmark_close: Optional[pd.Series] = None,
        benchmark_symbol: str = "",
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

        bb_period = min(20, max(5, n // 5))
        bb_u_all, bb_m_all, bb_l_all = _bollinger(close, period=bb_period)
        bbw_all = bollinger_bandwidth_pct(bb_m_all, bb_u_all, bb_l_all)

        adx_p = min(14, max(5, n // 4))
        st_p = min(10, max(5, n // 4))
        cmf_p = min(20, max(5, n // 3))
        hv_p = min(20, max(5, n // 3))
        ema_k = min(20, max(5, n // 5))
        rs_lb = min(20, max(5, n // 3))

        adx_s, plus_di_s, minus_di_s, _dx_s = adx_di(high, low, close, period=adx_p)
        st_line_s, st_dir_s = supertrend(high, low, close, period=st_p, multiplier=3.0)
        obv_s = obv(close, vol)
        cmf_s = chaikin_money_flow(high, low, close, vol, period=cmf_p)
        vwap_s = anchored_vwap(high, low, close, vol)
        kc_u_s, kc_m_s, kc_l_s = keltner_channels(
            close, high, low, ema_period=ema_k, atr_period=st_p, atr_mult=2.0
        )
        sq_s = squeeze_bb_inside_kc(bb_u_all, bb_l_all, kc_u_s, kc_l_s)
        hv_s = historical_volatility_annualized(close, period=hv_p)
        swing = swing_extreme_last_bar(high, low, window=min(5, max(3, n // 10)))

        def _fv(x: Optional[float]) -> Optional[float]:
            if x is None:
                return None
            if isinstance(x, (float, np.floating)) and (np.isnan(x) or np.isinf(x)):
                return None
            return float(x)

        adx_last = adx_s.iloc[-1]
        pdi_last = plus_di_s.iloc[-1]
        mdi_last = minus_di_s.iloc[-1]

        advanced: Dict[str, Any] = {
            "periods": {
                "adx": adx_p,
                "supertrend": st_p,
                "cmf": cmf_p,
                "hv": hv_p,
                "keltner_ema": ema_k,
                "bollinger": bb_period,
                "rs_lookback": rs_lb,
            },
            "adx": _fv(float(adx_last)) if pd.notna(adx_last) else None,
            "plus_di": _fv(float(pdi_last)) if pd.notna(pdi_last) else None,
            "minus_di": _fv(float(mdi_last)) if pd.notna(mdi_last) else None,
            "supertrend": _fv(st_line_s.iloc[-1]),
            "supertrend_direction": int(st_dir_s.iloc[-1]),
            "obv": _fv(obv_s.iloc[-1]),
            "obv_change_10": (
                _fv(float(obv_s.iloc[-1] - obv_s.iloc[-11]))
                if n >= 12
                else None
            ),
            "cmf": _fv(cmf_s.iloc[-1]),
            "anchored_vwap": _fv(vwap_s.iloc[-1]),
            "bb_bandwidth_pct": _fv(bbw_all.iloc[-1]),
            "keltner_upper": _fv(kc_u_s.iloc[-1]),
            "keltner_mid": _fv(kc_m_s.iloc[-1]),
            "keltner_lower": _fv(kc_l_s.iloc[-1]),
            "squeeze_on": bool(sq_s.iloc[-1]) if pd.notna(sq_s.iloc[-1]) else False,
            "hv_annualized_pct": _fv(float(hv_s.iloc[-1]) * 100.0) if pd.notna(hv_s.iloc[-1]) else None,
            "local_high_last": swing["local_high_last"],
            "local_low_last": swing["local_low_last"],
        }

        if benchmark_close is not None and len(benchmark_close) > 0 and not benchmark_close.empty:
            try:
                rs_d = relative_strength_vs_benchmark(close, benchmark_close, lookback=rs_lb)
                r_ratio = rs_d["rs_ratio_x100"].iloc[-1]
                r_chg = rs_d["rs_ratio_change_pct_vs_bench"].iloc[-1]
                advanced["vs_benchmark"] = {
                    "benchmark_symbol": benchmark_symbol or "",
                    "rs_ratio_times_100": _fv(float(r_ratio)) if pd.notna(r_ratio) else None,
                    "rs_ratio_change_lookback_pct": _fv(float(r_chg)) if pd.notna(r_chg) else None,
                }
            except Exception:
                advanced["vs_benchmark"] = {"benchmark_symbol": benchmark_symbol, "error": "alignment_failed"}

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
            "advanced": advanced,
        }

        notes: List[str] = []
        if n < 30:
            notes.append(f"Short history ({n} sessions) — indicators use shortened lookbacks.")
        if advanced.get("squeeze_on"):
            notes.append("Volatility squeeze: Bollinger bandwidth inside Keltner (potential expansion setup).")
        tr_lab = adx_regime_label(advanced.get("adx"))
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
                "trend_regime": tr_lab,
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

        p_chart: Dict[str, Any] = {
            **p,
            "bb_period_chart": bb_period,
            "adx_period_chart": adx_p,
            "supertrend_period_chart": st_p,
            "cmf_period_chart": cmf_p,
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
                p_chart,
                float(close.iloc[-1]),
                chart_extras={
                    "vwap": vwap_s,
                    "supertrend": st_line_s,
                    "keltner_upper": kc_u_s,
                    "keltner_lower": kc_l_s,
                    "adx": adx_s,
                    "plus_di": plus_di_s,
                    "minus_di": minus_di_s,
                },
                bb_upper_series=bb_u_all,
                bb_mid_series=bb_m_all,
                bb_lower_series=bb_l_all,
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
        *,
        chart_extras: Optional[Dict[str, pd.Series]] = None,
        bb_upper_series: Optional[pd.Series] = None,
        bb_mid_series: Optional[pd.Series] = None,
        bb_lower_series: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """OHLCV + aligned indicator series + pivot S/R for charting UIs.

        Uses the **full** analysis-window frame (chronological) so UI date ranges match the first/last
        candle. A hard cap exists only for pathological series length.
        """
        plot_df = df.sort_index().copy()
        if len(plot_df) > _CHART_HARD_CAP:
            plot_df = plot_df.iloc[-_CHART_HARD_CAP:].copy()
        idx = plot_df.index
        c_ = plot_df["Close"].astype(float)
        h_ = plot_df["High"].astype(float) if "High" in plot_df.columns else c_
        lo_ = plot_df["Low"].astype(float) if "Low" in plot_df.columns else c_
        if (
            bb_upper_series is not None
            and bb_mid_series is not None
            and bb_lower_series is not None
        ):
            bb_u = bb_upper_series.reindex(idx)
            bb_m = bb_mid_series.reindex(idx)
            bb_l = bb_lower_series.reindex(idx)
        else:
            bb_u, bb_m, bb_l = _bollinger(c_)
        st_k, st_d = _stochastic(h_, lo_, c_)

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

        ind_out: Dict[str, Any] = {
            "ma_short": _align(ma_s),
            "ma_long": _align(ma_l),
            "rsi": _align(rsi),
            "macd": _align(macd_line),
            "macd_signal": _align(macd_signal),
            "macd_histogram": _align(macd_hist),
            "volume": _align(vol),
            "bb_upper": _align(bb_u),
            "bb_mid": _align(bb_m),
            "bb_lower": _align(bb_l),
            "stoch_k": _align(st_k),
            "stoch_d": _align(st_d),
        }
        if chart_extras:
            for key, s in chart_extras.items():
                if isinstance(s, pd.Series) and not s.empty:
                    ind_out[key] = _align(s)

        bb_p = int(periods.get("bb_period_chart", 20))

        return {
            "bars": bars,
            "indicators": ind_out,
            "periods": {
                "ma_short": periods["ma_short"],
                "ma_long": periods["ma_long"],
                "rsi": periods["rsi"],
                "bb": bb_p,
                "stoch_k": 14,
                "adx": periods.get("adx_period_chart", 14),
                "supertrend": periods.get("supertrend_period_chart", 10),
                "cmf": periods.get("cmf_period_chart", 20),
            },
            "support_resistance": sr,
            "window": {
                "first_bar": _time_str(idx[0]) if len(idx) else None,
                "last_bar": _time_str(idx[-1]) if len(idx) else None,
                "rows": int(len(plot_df)),
            },
        }

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "symbol": "",
            "last": {},
            "labels": {"trend": "n/a", "momentum": "n/a", "volatility": "n/a", "trend_regime": "n/a"},
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
