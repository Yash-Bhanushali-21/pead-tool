"""
Fundamental analysis layer: valuation, quality, balance sheet, and growth screens.

Data is sourced primarily from Yahoo Finance (`ticker.info` + optional statements).
Outputs are research-style summaries — not investment advice.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _clip_score(x: float, lo: float = 0.0, hi: float = 25.0) -> float:
    return float(np.clip(x, lo, hi))


class FundamentalAnalyzer:
    """
    Builds ratio tables and simple 0–100 pillar scores from Yahoo fundamentals.

    Pillar weights (each 0–25): valuation, quality, balance_sheet, growth.
    """

    def analyze(
        self,
        symbol: str,
        company_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        symbol : str
            NSE symbol (e.g. RELIANCE)
        company_bundle : dict, optional
            Output of DataManager.get_company_fundamentals — used to skip re-fetching statements
        """
        try:
            import yfinance as yf
        except ImportError as e:
            raise RuntimeError("yfinance is required for fundamental analysis") from e

        from src.data.yahoo_fetcher import YahooDataFetcher

        ysym = YahooDataFetcher.nse_to_yahoo_symbol(symbol)
        ticker = yf.Ticker(ysym)
        info: Dict[str, Any] = dict(ticker.info or {})

        notes: List[str] = []
        if not info:
            notes.append("Yahoo returned empty quote info — ratios may be incomplete.")

        ratios, levels = self._extract_ratios(info)
        analyst = self._extract_analyst(info)

        scores, score_notes = self._score_pillars(ratios, info)
        notes.extend(score_notes)

        fundamental_score = sum(
            scores.get(k, 0) for k in ("valuation", "quality", "balance_sheet", "growth")
        )
        stance = self._stance(fundamental_score)

        out: Dict[str, Any] = {
            "symbol": symbol,
            "yahoo_symbol": ysym,
            "as_of": datetime.utcnow().isoformat() + "Z",
            "ratios": ratios,
            "levels": levels,
            "analyst": analyst,
            "scores": {
                **scores,
                "fundamental_score": round(fundamental_score, 2),
            },
            "stance": stance,
            "notes": notes,
            "raw_info_keys": len(info),
        }

        # Optional: attach statement freshness from bundle
        if company_bundle and company_bundle.get("financials"):
            out["has_financial_statements"] = True
        else:
            out["has_financial_statements"] = bool(company_bundle and company_bundle.get("financials"))

        return out

    def _extract_ratios(self, info: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ratios: Dict[str, Any] = {
            "pe_trailing": _f(info.get("trailingPE")),
            "pe_forward": _f(info.get("forwardPE")),
            "peg": _f(info.get("pegRatio")),
            "price_to_book": _f(info.get("priceToBook")),
            "price_to_sales": _f(info.get("priceToSalesTrailing12Months")),
            "ev_to_ebitda": _f(info.get("enterpriseToEbitda")),
            "ev_to_revenue": _f(info.get("enterpriseToRevenue")),
            "roe": _f(info.get("returnOnEquity")),  # 0–1 from Yahoo
            "roa": _f(info.get("returnOnAssets")),
            "gross_margin": _f(info.get("grossMargins")),
            "operating_margin": _f(info.get("operatingMargins")),
            "profit_margin": _f(info.get("profitMargins")),
            "debt_to_equity": _f(info.get("debtToEquity")),
            "current_ratio": _f(info.get("currentRatio")),
            "quick_ratio": _f(info.get("quickRatio")),
            "revenue_growth": _f(info.get("revenueGrowth")),
            "earnings_growth": _f(info.get("earningsGrowth")),
            "earnings_quarterly_growth": _f(info.get("earningsQuarterlyGrowth")),
        }
        mcap = _f(info.get("marketCap"))
        fcf = _f(info.get("freeCashflow"))
        if mcap and fcf and mcap > 0:
            ratios["fcf_yield"] = fcf / mcap
        else:
            ratios["fcf_yield"] = None

        levels = {
            "market_cap": _f(info.get("marketCap")),
            "enterprise_value": _f(info.get("enterpriseValue")),
            "total_debt": _f(info.get("totalDebt")),
            "total_cash": _f(info.get("totalCash")),
            "shares_outstanding": _f(info.get("sharesOutstanding")),
            "float_shares": _f(info.get("floatShares")),
            "beta": _f(info.get("beta")),
            "52w_high": _f(info.get("fiftyTwoWeekHigh")),
            "52w_low": _f(info.get("fiftyTwoWeekLow")),
            "current_price": _f(info.get("currentPrice") or info.get("regularMarketPrice")),
        }
        return ratios, levels

    def _extract_analyst(self, info: Dict[str, Any]) -> Dict[str, Any]:
        rec = _f(info.get("recommendationMean"))
        return {
            "recommendation_mean": rec,
            "recommendation_key": info.get("recommendationKey"),
            "target_mean_price": _f(info.get("targetMeanPrice")),
            "target_high": _f(info.get("targetHighPrice")),
            "target_low": _f(info.get("targetLowPrice")),
            "num_analysts": int(info.get("numberOfAnalystOpinions") or 0) or None,
        }

    def _score_pillars(
        self, ratios: Dict[str, Any], info: Dict[str, Any]
    ) -> Tuple[Dict[str, float], List[str]]:
        notes: List[str] = []

        # --- Valuation (lower PE / reasonable PEG / not extreme EV/EBITDA) ---
        v = 12.5
        pe = ratios.get("pe_trailing")
        fpe = ratios.get("pe_forward")
        peg = ratios.get("peg")
        ev_e = ratios.get("ev_to_ebitda")

        if pe is not None and pe < 0:
            notes.append("Negative trailing P/E (loss-making) — valuation pillar discounted.")
            v = 8.0
        elif pe is not None:
            if pe <= 12:
                v = 20.0
            elif pe <= 18:
                v = 17.0
            elif pe <= 28:
                v = 13.0
            elif pe <= 45:
                v = 9.0
            else:
                v = 5.0
        elif fpe is not None:
            if fpe <= 14:
                v = 17.0
            elif fpe <= 22:
                v = 14.0
            else:
                v = 10.0
        else:
            notes.append("P/E unavailable — valuation inferred from other fields only.")
            v = 10.0

        if peg is not None:
            if peg < 1.0:
                v = min(25.0, v + 3.0)
            elif peg > 2.5:
                v = max(0.0, v - 4.0)

        if ev_e is not None and ev_e > 0:
            if ev_e <= 10:
                v = min(25.0, v + 2.0)
            elif ev_e >= 25:
                v = max(0.0, v - 3.0)

        v = _clip_score(v)

        # --- Quality (margins + ROE/ROA) ---
        q = 10.0
        roe = ratios.get("roe")
        roa = ratios.get("roa")
        om = ratios.get("operating_margin")
        pm = ratios.get("profit_margin")

        if roe is not None:
            q += _clip_score(roe * 40.0, 0, 8.0)
        if roa is not None:
            q += _clip_score(roa * 30.0, 0, 5.0)
        if om is not None:
            q += _clip_score(om * 25.0, 0, 6.0)
        elif pm is not None:
            q += _clip_score(pm * 25.0, 0, 6.0)
        q = _clip_score(q)

        # --- Balance sheet ---
        b = 12.5
        de = ratios.get("debt_to_equity")
        cr = ratios.get("current_ratio")
        qr = ratios.get("quick_ratio")

        if de is not None:
            if de < 0.3:
                b = 22.0
            elif de < 0.8:
                b = 19.0
            elif de < 1.5:
                b = 15.0
            elif de < 2.5:
                b = 11.0
            else:
                b = 6.0
        if cr is not None:
            if cr >= 1.5:
                b = min(25.0, b + 2.0)
            elif cr < 1.0:
                b = max(0.0, b - 4.0)
        if qr is not None and qr < 0.8:
            b = max(0.0, b - 2.0)
        b = _clip_score(b)

        # --- Growth ---
        g = 10.0
        rg = ratios.get("revenue_growth")
        eg = ratios.get("earnings_growth")
        eqg = ratios.get("earnings_quarterly_growth")

        def _growth_pts(x: Optional[float]) -> float:
            if x is None:
                return 0.0
            if x > 0.20:
                return 8.0
            if x > 0.10:
                return 6.0
            if x > 0.03:
                return 4.0
            if x > 0:
                return 2.0
            if x > -0.05:
                return 0.0
            return -3.0

        g += _growth_pts(rg) + _growth_pts(eg) * 0.5
        if eqg is not None:
            g += _clip_score(eqg * 10.0, -4.0, 4.0)
        g = _clip_score(g)

        return (
            {
                "valuation": round(v, 2),
                "quality": round(q, 2),
                "balance_sheet": round(b, 2),
                "growth": round(g, 2),
            },
            notes,
        )

    def _stance(self, fundamental_score: float) -> str:
        if fundamental_score >= 65:
            return (
                "Screening: fundamentals skew relatively supportive vs typical thresholds "
                "(not a buy recommendation)."
            )
        if fundamental_score >= 45:
            return "Screening: mixed fundamentals — combine with PEAD, risk, and liquidity."
        return "Screening: fundamentals skew cautious for long exposure — verify thesis."

    def format_report(self, data: Dict[str, Any]) -> str:
        """Plain-text report for console / file."""
        lines: List[str] = []
        lines.append("")
        lines.append("=" * 72)
        lines.append("FUNDAMENTAL ANALYSIS (screening layer — not investment advice)")
        lines.append("=" * 72)
        lines.append("")
        lines.append(f"Symbol: {data.get('yahoo_symbol', data.get('symbol'))}")
        lines.append(f"As of:  {data.get('as_of', '')}")
        sc = data.get("scores", {})
        lines.append(
            f"Fundamental score (0–100): {sc.get('fundamental_score', 0):.1f}  "
            f"[Val {sc.get('valuation', 0):.0f} | Qual {sc.get('quality', 0):.0f} | "
            f"BS {sc.get('balance_sheet', 0):.0f} | Gr {sc.get('growth', 0):.0f}]"
        )
        lines.append(f"Stance: {data.get('stance', '')}")
        lines.append("")
        lines.append("Key ratios")
        lines.append("-" * 72)
        r = data.get("ratios", {})
        order = [
            ("P/E (trailing)", "pe_trailing"),
            ("P/E (forward)", "pe_forward"),
            ("PEG", "peg"),
            ("P/B", "price_to_book"),
            ("EV / EBITDA", "ev_to_ebitda"),
            ("ROE", "roe"),
            ("ROA", "roa"),
            ("Operating margin", "operating_margin"),
            ("Net margin", "profit_margin"),
            ("Debt / Equity", "debt_to_equity"),
            ("Current ratio", "current_ratio"),
            ("Revenue growth (YoY)", "revenue_growth"),
            ("Earnings growth (YoY)", "earnings_growth"),
            ("FCF yield (approx)", "fcf_yield"),
        ]
        for label, key in order:
            val = r.get(key)
            if val is None:
                lines.append(f"  {label:28}  —")
            elif key in ("roe", "roa", "gross_margin", "operating_margin", "profit_margin"):
                lines.append(f"  {label:28}  {val * 100:.2f}%")
            elif key in ("revenue_growth", "earnings_growth", "earnings_quarterly_growth", "fcf_yield"):
                lines.append(f"  {label:28}  {val * 100:.2f}%")
            else:
                lines.append(f"  {label:28}  {val:.4g}")

        lines.append("")
        lines.append("Levels")
        lines.append("-" * 72)
        lv = data.get("levels", {})
        for label, key, fmt in [
            ("Market cap", "market_cap", "{:,.0f}"),
            ("Enterprise value", "enterprise_value", "{:,.0f}"),
            ("Beta", "beta", "{:.3f}"),
            ("52w high", "52w_high", "{:.4f}"),
            ("52w low", "52w_low", "{:.4f}"),
            ("Last price (info)", "current_price", "{:.4f}"),
        ]:
            v = lv.get(key)
            lines.append(f"  {label:28}  " + (fmt.format(v) if v is not None else "—"))

        an = data.get("analyst", {})
        lines.append("")
        lines.append("Analyst snapshot (Yahoo)")
        lines.append("-" * 72)
        rm = an.get("recommendation_mean")
        lines.append(
            f"  {'Recommendation (1=buy,5=sell)':28}  "
            + (f"{rm:.2f}" if rm is not None else "—")
        )
        lines.append(
            f"  {'Target mean':28}  "
            + (
                f"{an.get('target_mean_price'):.4g}"
                if an.get("target_mean_price") is not None
                else "—"
            )
        )
        lines.append(
            f"  {'# analysts':28}  {an.get('num_analysts') or '—'}"
        )

        if data.get("notes"):
            lines.append("")
            lines.append("Notes")
            lines.append("-" * 72)
            for n in data["notes"]:
                lines.append(f"  • {n}")

        lines.append("")
        lines.append(
            "Use with PEAD outputs: fundamentals = slow/lens; PEAD = event window. "
            "Always size risk and check liquidity."
        )
        lines.append("=" * 72)
        lines.append("")
        return "\n".join(lines)

    def to_json(self, data: Dict[str, Any]) -> str:
        """JSON for machine-readable export (ratios only; no giant raw info)."""
        export = {
            k: data[k]
            for k in (
                "symbol",
                "yahoo_symbol",
                "as_of",
                "ratios",
                "levels",
                "analyst",
                "scores",
                "stance",
                "notes",
            )
            if k in data
        }
        return json.dumps(export, indent=2, default=str)
