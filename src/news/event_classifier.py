"""
Rule-based event type classifier for Indian equity news articles.

Assigns each article one of the following event types based on title + summary
keyword matching.  No LLM, no model download — pure deterministic logic.

Event taxonomy:
  EARNINGS          quarterly/annual results, PAT, EPS, revenue beats/misses
  GUIDANCE          management outlook, FY target, capex plans, commentary
  ANALYST_RATING    broker target price, rating upgrades/downgrades
  CORPORATE_ACTION  dividend, bonus, split, buyback, rights issue
  M_AND_A           merger, acquisition, stake sale, JV, demerger
  REGULATORY        SEBI, NCLT, court order, penalty, ED/CBI, compliance
  MANAGEMENT        CEO/CFO/MD change, board appointment, promoter activity
  MACRO_INDIA       RBI, budget, GDP, inflation, FII/DII, crude, rupee, rate
  SECTOR_CONTEXT    sector-wide news without company-specific event
  GENERAL           unclassified (default)

Classification is deterministic: first matching rule wins (rules ordered by
decreasing specificity so rare events like M&A don't get shadowed by generic ones).
"""
from __future__ import annotations

import re
from typing import List, Tuple

from src.news.collector import NewsArticle

EventType = str  # string literal from the taxonomy above

# ── Keyword rule sets ──────────────────────────────────────────────────────────
# Each rule: (EventType, compiled regex)
# Regexes are word-boundary aware for short keywords to avoid false matches.

def _kw(*words: str) -> re.Pattern:
    parts = [rf"\b{re.escape(w)}\b" for w in words]
    return re.compile("|".join(parts), re.IGNORECASE)


_RULES: List[Tuple[str, re.Pattern]] = [
    # ── CORPORATE_ACTION (before EARNINGS to catch "dividend results")
    ("CORPORATE_ACTION", _kw(
        "dividend", "buyback", "buy-back", "buy back", "bonus share", "stock split",
        "rights issue", "rights entitlement", "open offer", "delisting",
        "share repurchase", "interim dividend", "final dividend", "special dividend",
        "record date", "ex-dividend", "ex-date",
    )),
    # ── M_AND_A
    ("M_AND_A", _kw(
        "merger", "acquisition", "acqui", "takeover", "stake sale", "divestment",
        "divestiture", "joint venture", "JV", "demerger", "spin-off", "spinoff",
        "slump sale", "strategic investment", "minority stake", "controlling stake",
        "open offer", "amalgamation", "scheme of arrangement",
    )),
    # ── REGULATORY
    ("REGULATORY", _kw(
        "SEBI", "NCLT", "NCLAT", "ED ", "Enforcement Directorate", "CBI",
        "Income Tax", "tax notice", "show cause", "penalty", "fine imposed",
        "court order", "contempt", "adjudication", "regulatory", "compliance",
        "SFIO", "insolvency", "liquidation", "IBC", "RERA", "RoC",
    )),
    # ── MANAGEMENT
    ("MANAGEMENT", _kw(
        "CEO", "CFO", "MD ", "managing director", "chairman", "board appoints",
        "board approves", "director resign", "executive resign", "promoter pledge",
        "promoter stake", "insider trading", "KMP change", "CTO appoint",
    )),
    # ── ANALYST_RATING
    ("ANALYST_RATING", _kw(
        "target price", "price target", "rating upgrade", "rating downgrade",
        "upgrade to buy", "downgrade to sell", "overweight", "underweight",
        "outperform", "underperform", "hold rating", "buy rating", "sell rating",
        "initiates coverage", "initiating coverage", "analyst", "brokerage",
        "PT raised", "PT cut", "PT lowered",
    )),
    # ── GUIDANCE
    ("GUIDANCE", _kw(
        "guidance", "outlook", "forecast", "management commentary", "FY target",
        "capex plan", "growth target", "annual target", "revenue guidance",
        "margin outlook", "management meets", "investor meet", "concall",
        "conference call", "AGM", "annual general meeting",
    )),
    # ── EARNINGS (after guidance/action so specific beats win over generic growth)
    ("EARNINGS", _kw(
        "quarterly results", "Q1 results", "Q2 results", "Q3 results", "Q4 results",
        "annual results", "quarterly profit", "net profit", "PAT", "EPS",
        "earnings per share", "revenue grew", "revenue fell", "beats estimate",
        "misses estimate", "beats expectations", "misses expectations",
        "profit rises", "profit falls", "profit surges", "profit drops",
        "EBITDA", "operating profit", "top line", "bottom line",
        "financial results", "results declared", "results announced",
    )),
    # ── MACRO_INDIA
    ("MACRO_INDIA", _kw(
        "RBI", "repo rate", "monetary policy", "MPC", "inflation", "CPI", "WPI",
        "GDP", "budget", "fiscal deficit", "FII", "DII", "foreign inflow",
        "crude oil", "Brent", "rupee", "INR", "dollar", "Fed rate",
        "US Fed", "bond yield", "10-year yield", "current account",
        "trade deficit", "PMI", "IIP", "GST collection", "disinvestment",
        "SEBI circular", "Nifty 50 outlook", "Sensex outlook",
    )),
    # ── SECTOR_CONTEXT (broad sector but no company-specific event)
    ("SECTOR_CONTEXT", _kw(
        "sector outlook", "industry outlook", "sector rally", "sector selloff",
        "banking sector", "IT sector", "pharma sector", "auto sector",
        "FMCG sector", "metal sector", "realty sector", "energy sector",
        "telecom sector", "sector rotation", "midcap rally", "smallcap rally",
    )),
]


def classify_event(article: NewsArticle) -> str:
    """Return the event type for a single article. Defaults to GENERAL."""
    text = f"{article.title} {article.summary}".strip()
    for event_type, pattern in _RULES:
        if pattern.search(text):
            return event_type
    return "GENERAL"


def classify_articles(articles: List[NewsArticle]) -> List[str]:
    """Return list of event types parallel to the input articles list."""
    return [classify_event(a) for a in articles]
