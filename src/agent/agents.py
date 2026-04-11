"""
Multi-agent research stack (PydanticAI):
- Coordinator: routes user intent and calls quant tools.
- Synthesis desk: second agent that polishes raw JSON into desk-style prose (invoked via tool).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic_ai import Agent, RunContext

from src.agent.announcements import get_latest_announcement_date
from src.agent.deps import ResearchDeps
from src.agent.serialize import compact_pead_for_llm, json_dumps_safe
from src.config.settings import config
from src.news.layer import run_news_sentiment_layer
from src.trade_context.snapshot import fetch_light_trade_context

logger = logging.getLogger(__name__)

COORDINATOR_INSTRUCTIONS = """You are the lead equity research coordinator for Indian NSE-listed stocks (institutional desk workflow — not regulated research).

You work with specialist capabilities exposed as tools:
- **News & sentiment scan** — RSS/Yahoo headlines + TextBlob / optional OpenAI blended score (`news_sentiment` JSON). Fast; no PEAD, CARs, or fundamentals. Use when the user asks for "news", "sentiment", "headlines", "news layer", or "scan the tape" on a symbol, or says to use the news/sentiment tool specifically.
- Resolve the earnings/event anchor date when the user does not provide one.
- Run the full PEAD + fundamentals + technical + optional news pipeline (heavy; use when a full event-study / valuation / CAR desk view is needed — not required for a pure news ask).
- **Execution context snapshot** — fast liquidity / volatility / alignment screen from price history only (no full PEAD); use when the user asks about sizing context, tape quality, or risk before committing time to a full run.
- **Yahoo calendar snippet** — best-effort next earnings / calendar fields (may be empty).
- **Synthesis desk** — turns raw tool JSON into polished institutional prose (memos, "verdict", broker-style narrative framing).

News-first workflow (critical):
1) If the user's ask is primarily about news/sentiment on one or more symbols, call `run_news_and_sentiment` for each symbol (default lookback ~90 days, max articles ~80 unless they specify otherwise).
2) When they want a **verdict**, **summary**, **what it means**, **broker-style read**, **desk note**, **implications**, or similar — after you have the tool JSON, you MUST call `ask_synthesis_desk` and pass a single string that starts with the line `TASK: NEWS_DESK_VERDICT` followed by a newline, then the exact JSON from `run_news_and_sentiment` (or multiple JSON objects if they asked for multiple names). Do not invent scores; the synthesis model only sees what you pass.
3) If they only wanted raw data, you may summarize briefly from the tool output without synthesis — but still no buy/sell language.

Rules:
- Never fabricate prices, CAR values, filing facts, or headline counts; only cite numbers that appear in tool outputs.
- Never state or imply a buy/sell recommendation; frame outputs as research inputs and execution context only.
- Do not claim you work for or represent any named asset manager or bank (e.g. BlackRock, Blackstone, Goldman) — keep a generic institutional voice.
- Prefer one focused PEAD run per symbol unless the user explicitly compares multiple names or dates.
- If data is missing or the tool returns an error, say so plainly and suggest what the user could change (symbol, date, or try again later).
- Remind users that outputs are research aids, not investment advice.

Be concise in the chat; use the synthesis desk when the user wants long-form prose or a verdict-style note."""


SYNTHESIS_INSTRUCTIONS = """You are the synthesis desk for an Indian equities research assistant.

You receive raw JSON from our tools. The payload may be full PEAD + fundamentals + technicals + news, **or** a news-only scan (`success`, `symbol`, `article_count`, `articles_preview`, `news_sentiment`).

**If the user message (or a line at the top) starts with `TASK: NEWS_DESK_VERDICT`:** write an institutional **desk verdict** on the news/sentiment evidence only. Use this structure in Markdown:

## Headline & narrative read
2–4 sentences: what the sampled headlines collectively suggest (bias, themes, gaps — headlines are incomplete vs filings).

## Sentiment & flow (tool-bound)
Interpret `news_sentiment` fields (e.g. `news_score_0_100`, any LLM summary fields) using **only** numbers/text present in the JSON. If a field is missing, say so.

## Risks & blind spots
Bullets: stale headlines, event risk, liquidity, sector/market correlation, why tape sentiment can diverge from fundamentals.

## Hypothetical positioning discussion (non-prescriptive)
Short bullets on how a **generic** institutional reader might frame risk/reward *as a thought experiment* — not instructions to trade. No "buy/sell/hold now."

## One-line verdict
A single balanced sentence capturing tone vs uncertainty.

End with: *Research commentary only — not investment advice.*

Tone: crisp sell-side / buy-side desk note — but **do not** name or claim affiliation with BlackRock, Blackstone, or any real firm.

---

**For all other inputs** (full PEAD-style JSON): executive summary, key numbers, risks, liquidity/volatility caveats, and what would change the view. Same honesty rules: do not invent statistics.

Never invent statistics. If the input lacks a figure, do not guess.
Not investment advice. No buy/sell imperative language."""


def build_synthesis_agent(model: Optional[str] = None) -> Agent[None, str]:
    m = model or config.AGENT_SYNTHESIS_MODEL
    return Agent(
        m,
        output_type=str,
        system_prompt=SYNTHESIS_INSTRUCTIONS,
    )


def build_coordinator_agent(
    synthesis_agent: Agent[None, str],
    model: Optional[str] = None,
) -> Agent[ResearchDeps, str]:
    m = model or config.AGENT_MODEL
    coordinator = Agent(
        m,
        deps_type=ResearchDeps,
        output_type=str,
        end_strategy="exhaustive",
        system_prompt=COORDINATOR_INSTRUCTIONS,
    )

    @coordinator.tool
    async def resolve_earnings_event_date(
        ctx: RunContext[ResearchDeps],
        symbol: str,
    ) -> str:
        """Find the latest plausible earnings announcement date for an NSE symbol (YYYY-MM-DD or error message)."""
        sym = symbol.strip().upper()
        dt = get_latest_announcement_date(sym, ctx.deps.analyzer.data_manager)
        if dt is None:
            return (
                f"Could not auto-resolve an announcement date for {sym}. "
                "Ask the user for an explicit YYYY-MM-DD anchor or verify the symbol."
            )
        return pd.Timestamp(dt).strftime("%Y-%m-%d")

    @coordinator.tool
    async def run_news_and_sentiment(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        lookback_days: int = 90,
        max_articles: int = 80,
    ) -> str:
        """
        Headline collection (Yahoo + Google News RSS) + TextBlob / optional OpenAI sentiment blend.
        Returns JSON: article_count, articles_preview, news_sentiment — **no PEAD, CARs, or fundamentals**.
        Use when the user asks for news scan, sentiment, or headlines on an NSE symbol.
        """
        sym = symbol.strip().upper()

        def _run():
            return run_news_sentiment_layer(
                ctx.deps.analyzer,
                sym,
                lookback_days=int(lookback_days),
                max_articles=int(max_articles),
            )

        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(None, _run)
        return json_dumps_safe(payload)

    @coordinator.tool
    async def run_full_pead_pipeline(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        announcement_date: Optional[str] = None,
        include_news: bool = True,
        generate_charts: bool = False,
    ) -> str:
        """
        Run the full PEAD study: event model, CARs, fundamentals, technicals, optional news sentiment, research brief.
        announcement_date: optional ISO date (YYYY-MM-DD); if omitted, auto-detects latest earnings date.
        Set generate_charts true only if the user explicitly wants image files (slower).
        """
        sym = symbol.strip().upper()
        ann: Optional[datetime] = None
        if announcement_date:
            ann = pd.to_datetime(announcement_date).to_pydatetime()
        else:
            ann_raw = get_latest_announcement_date(sym, ctx.deps.analyzer.data_manager)
            if ann_raw is None:
                return json_dumps_safe(
                    {
                        "success": False,
                        "error": "No announcement date provided and auto-detection failed.",
                    }
                )
            ann = pd.Timestamp(ann_raw).to_pydatetime()

        out_dir = str(ctx.deps.output_base)

        def _run():
            return ctx.deps.analyzer.analyze_announcement(
                sym,
                ann,
                visualize=generate_charts,
                output_dir=out_dir,
                include_news=include_news,
                news_lookback_days=config.NEWS_LOOKBACK_DAYS,
            )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run)
        compact = compact_pead_for_llm(result)
        return json_dumps_safe(compact)

    @coordinator.tool
    async def ask_synthesis_desk(
        ctx: RunContext[ResearchDeps],
        raw_research_payload: str,
    ) -> str:
        """
        Delegate to the Synthesis sub-agent: turns raw JSON / bullet notes from tools into polished desk prose.
        For a news-only verdict, prefix the payload with a line ``TASK: NEWS_DESK_VERDICT`` then the JSON from
        ``run_news_and_sentiment`` (see coordinator instructions).
        """
        text = (raw_research_payload or "").strip()
        if len(text) > 60000:
            text = text[:60000] + "\n...[truncated for synthesis desk]"
        sub = await synthesis_agent.run(text)
        return sub.output

    @coordinator.tool
    async def get_execution_context_snapshot(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        lookback_days: int = 200,
    ) -> str:
        """
        Fast execution-context snapshot: volume vs average, ATR% / volatility band, technical stance.
        Does **not** run PEAD, fundamentals, or news — use for a quick tape-quality check or before a full run.
        """
        sym = symbol.strip().upper()

        def _run():
            return fetch_light_trade_context(
                sym,
                ctx.deps.analyzer.data_manager,
                lookback_calendar_days=int(lookback_days),
            )

        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(None, _run)
        return json_dumps_safe(payload)

    @coordinator.tool
    async def get_yahoo_calendar_snippet(
        ctx: RunContext[ResearchDeps],
        symbol: str,
    ) -> str:
        """Best-effort Yahoo Finance calendar / earnings fields for the NSE symbol (often sparse)."""

        def _run():
            import yfinance as yf

            sym = symbol.strip().upper()
            t = yf.Ticker(f"{sym}.NS")
            out: dict = {"symbol": sym}
            cal = getattr(t, "calendar", None)
            if cal is not None and hasattr(cal, "empty") and not cal.empty:
                out["calendar"] = cal.to_dict() if hasattr(cal, "to_dict") else str(cal)
            ed = getattr(t, "earnings_dates", None)
            if ed is not None and hasattr(ed, "empty") and not ed.empty:
                out["earnings_dates_head"] = ed.head(6).to_string()
            return out

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    return coordinator
