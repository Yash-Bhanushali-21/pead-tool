"""
Multi-agent research stack (PydanticAI):
- Coordinator: routes user intent and calls quant tools.
- Synthesis desk: second agent that polishes raw JSON into desk-style prose (invoked via tool).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic_ai import Agent, RunContext

from src.agent.announcements import get_latest_announcement_date
from src.agent.deps import ResearchDeps
from src.agent.serialize import compact_pead_for_llm, json_dumps_safe
from src.config.config import config
from src.news.layer import run_news_sentiment_layer
from src.tools.executions import (
    execute_document_pdf,
    execute_execution_snapshot,
    execute_fundamentals,
    execute_recent_announcements,
    execute_scoring_only,
    execute_technical,
    execute_trade_readiness_isolated,
    execute_yahoo_calendar,
)

logger = logging.getLogger(__name__)

COORDINATOR_INSTRUCTIONS = """You are the lead equity research coordinator for Indian NSE-listed stocks (institutional desk workflow — not regulated research).

## Tools (same capabilities as the web **Tools** pages — you MUST call them when the user asks to "use the X tool", "run fundamentals", "technical on …", etc.)
| User intent | Tool | Notes |
|-------------|------|------|
| Fundamentals / screening / ratios / Yahoo bundle | `run_fundamentals_screening` | Symbol only |
| Technicals (RSI, MACD, MAs, pivots) | `run_technical_snapshot` | Defaults: PEAD event window, auto announcement date, include_chart on |
| News & sentiment headlines | `run_news_and_sentiment` | Defaults: ~90d lookback, 80 articles |
| Equity research bundle (+ optional desk LLM) | `run_full_pead_pipeline` | **range_start**, **range_end**; optional **include_desk_insight**, **include_market_sentiment** (defaults true) |
| CARs + component scores only | `run_scoring_only_stack` | Optional announcement_date (else auto) |
| Trade readiness pillars (isolated) | `run_trade_readiness_tool` | lookback_days default 200 |
| Full execution / tape context JSON | `get_execution_context_snapshot` | Same as Tools → execution snapshot |
| Yahoo earnings calendar | `get_yahoo_calendar_snippet` | |
| Parse announcement PDF on disk | `run_document_pdf_parse` | **Requires** YYYY-MM-DD |
| Top N recent NSE names batch | `run_recent_nse_announcements` | Slower; default top_n=8 |
| Polish prose | `ask_synthesis_desk` | After you have JSON |

## Confirmation UX (critical)
- If the request is **ambiguous** (which symbol? which tool? missing PDF date?) or would **start an expensive run** without a clear symbol, **do not** call the tool yet. Reply with one short clarifying question.
- When you need the user to confirm a specific run, end your message with **exactly one** line containing this HTML comment (valid JSON inside):
  `<!--TOOL_CONFIRM:{"tool":"<id>","args":{...},"label":"short human label"}-->`
  `<id>` must be one of: run_fundamentals_screening, run_technical_snapshot, run_scoring_only_stack, run_trade_readiness_tool, run_document_pdf_parse, run_recent_nse_announcements, run_news_and_sentiment, run_full_pead_pipeline, get_execution_context_snapshot, get_yahoo_calendar_snippet. Put all parameters needed to run the tool in `args` (e.g. {"symbol":"RELIANCE","range_start":"2025-10-01","range_end":"2026-04-17"} for the equity bundle).
- When the user replies **yes / y / sure / ok / confirm / go ahead / proceed** right after such a prompt (or clearly confirms), **call the tool** immediately with those args. If they say no, do not run it.

## News verdict workflow
1) For news/sentiment-first asks, call `run_news_and_sentiment`.
2) For a desk verdict on that output, call `ask_synthesis_desk` with a line `TASK: NEWS_DESK_VERDICT` then the JSON from the news tool.

## Rules
- Never fabricate prices, CAR values, filing facts, or headline counts; only cite numbers from tool outputs.
- Never state or imply a buy/sell recommendation.
- Do not claim affiliation with any named asset manager or bank.
- If a tool errors, say so plainly and suggest fixes (symbol, date, wider range).
- Outputs are research aids, not investment advice.

Be concise; use `ask_synthesis_desk` for long-form memos."""


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
        scrape_bodies: bool = True,
        max_scrape: int = 32,
        end_date_iso: Optional[str] = None,
        include_ai_digest: bool = True,
    ) -> str:
        """
        Yahoo + Google News RSS, optional **full article scrape** (first ``max_scrape`` URLs via trafilatura),
        TextBlob + optional OpenAI blend, **bullish/bearish/neutral** aggregate label in ``news_sentiment``.

        Returns JSON: window, article_count, articles_preview (with body_preview when scraped), scrape stats,
        news_sentiment (includes stock_media_stance, per_article, stance_summary) — **no PEAD/CARs/fundamentals**.
        """
        sym = symbol.strip().upper()

        def _run():
            end_dt = None
            if end_date_iso:
                try:
                    end_dt = pd.Timestamp(end_date_iso).to_pydatetime()
                except Exception:
                    end_dt = None
            return run_news_sentiment_layer(
                ctx.deps.analyzer,
                sym,
                lookback_days=int(lookback_days),
                max_articles=int(max_articles),
                end_date=end_dt,
                scrape_bodies=bool(scrape_bodies),
                max_scrape=int(max_scrape),
                include_ai_digest=bool(include_ai_digest),
            )

        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(None, _run)
        return json_dumps_safe(payload)

    @coordinator.tool
    async def run_full_pead_pipeline(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        range_start: str,
        range_end: str,
        include_news: bool = True,
        generate_charts: bool = False,
        include_desk_insight: bool = True,
        include_market_sentiment: bool = True,
    ) -> str:
        """
        Run the equity research bundle: fundamentals + technicals (Tools paths) + optional news + trade context.

        ``range_start`` / ``range_end`` are YYYY-MM-DD inclusive — the **same** calendar window is used
        for OHLCV fetch, technical (including chart payload), news article filtering, and trade-context
        price input. Fundamentals remain a company snapshot (not day-by-day over the range).

        Set ``generate_charts`` true only if the user explicitly wants image files (slower).
        ``include_desk_insight`` runs the consolidated research-desk LLM step (requires API key).
        ``include_market_sentiment`` adds a broader India/market headline pass in the same window.
        """
        sym = symbol.strip().upper()
        try:
            rs = pd.Timestamp(str(range_start).strip()).normalize().to_pydatetime()
            re0 = pd.Timestamp(str(range_end).strip()).normalize().to_pydatetime()
            re = re0.replace(hour=23, minute=59, second=59, microsecond=999999)
        except Exception as e:
            return json_dumps_safe(
                {"success": False, "error": f"Invalid range_start/range_end: {e}"}
            )
        if rs > re0:
            return json_dumps_safe(
                {"success": False, "error": "range_start must be on or before range_end."}
            )

        out_dir = str(ctx.deps.output_base)

        def _run():
            return ctx.deps.analyzer.analyze_equity_research(
                sym,
                rs,
                re,
                visualize=generate_charts,
                output_dir=out_dir,
                include_news=include_news,
                news_lookback_days=config.NEWS_LOOKBACK_DAYS,
                include_desk_insight=include_desk_insight,
                include_market_sentiment=include_market_sentiment,
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
        Full execution-context snapshot (tape / liquidity / vol / alignment) — same as Tools → execution snapshot.
        Does **not** run PEAD fundamentals pipeline — use for quick sizing / tape context.
        """
        sym = symbol.strip().upper()

        def _run():
            return execute_execution_snapshot(
                ctx.deps.analyzer,
                sym,
                int(lookback_days),
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
            return execute_yahoo_calendar(symbol)

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    @coordinator.tool
    async def run_fundamentals_screening(
        ctx: RunContext[ResearchDeps],
        symbol: str,
    ) -> str:
        """Fundamental screening (pillar scores, ratios) from Yahoo/NSE bundle — same as Tools → Fundamentals."""

        def _run():
            return execute_fundamentals(ctx.deps.analyzer, symbol)

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    @coordinator.tool
    async def run_technical_snapshot(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        price_window: Literal["pead_event", "explicit_range"] = "pead_event",
        announcement_resolution: Literal["auto", "manual"] = "auto",
        announcement_date: Optional[str] = None,
        range_start: Optional[str] = None,
        range_end: Optional[str] = None,
        include_chart: bool = True,
        include_ai_verdict: bool = False,
    ) -> str:
        """
        Post-event technical snapshot (RSI, MACD, MAs, ATR%, pivot S/R) — same as Tools → Technical.
        Defaults match the UI: PEAD event window + auto announcement date unless manual/range is set.
        """

        def _run():
            return execute_technical(
                ctx.deps.analyzer,
                symbol=symbol.strip().upper(),
                price_window=price_window,
                announcement_resolution=announcement_resolution,
                announcement_date=announcement_date,
                range_start=range_start,
                range_end=range_end,
                include_chart=include_chart,
                include_ai_verdict=include_ai_verdict,
            )

        loop = asyncio.get_running_loop()
        out = await loop.run_in_executor(None, _run)
        return json_dumps_safe(out)

    @coordinator.tool
    async def run_scoring_only_stack(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        announcement_date: Optional[str] = None,
    ) -> str:
        """CARs + five PEAD component scores + composite — same as Tools → Scoring (no full technical/news)."""

        def _run():
            return execute_scoring_only(ctx.deps.analyzer, symbol, announcement_date)

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    @coordinator.tool
    async def run_trade_readiness_tool(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        lookback_days: int = 200,
    ) -> str:
        """Trade readiness pillars only — same as Tools → Trade readiness (isolated)."""

        def _run():
            return execute_trade_readiness_isolated(
                ctx.deps.analyzer,
                symbol.strip().upper(),
                int(lookback_days),
            )

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    @coordinator.tool
    async def run_document_pdf_parse(
        ctx: RunContext[ResearchDeps],
        symbol: str,
        announcement_date: str,
    ) -> str:
        """
        Parse an announcement PDF already on disk (NSE naming convention) — same as Tools → Document PDF.
        announcement_date: YYYY-MM-DD (required).
        """

        def _run():
            return execute_document_pdf(
                ctx.deps.analyzer,
                symbol.strip().upper(),
                announcement_date.strip(),
            )

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    @coordinator.tool
    async def run_recent_nse_announcements(
        ctx: RunContext[ResearchDeps],
        top_n: int = 8,
        include_news: bool = True,
        visualize: bool = False,
    ) -> str:
        """
        Batch scan of top N recent NSE announcements — same as Tools → PEAD recent (can be slow).
        Writes under the chat agent output directory.
        """

        out_dir = str(ctx.deps.output_base)

        def _run():
            return execute_recent_announcements(
                ctx.deps.analyzer,
                int(top_n),
                visualize=visualize,
                output_dir=out_dir,
                include_news=include_news,
                news_lookback_days=config.NEWS_LOOKBACK_DAYS,
                news_max_articles=config.NEWS_MAX_ARTICLES,
            )

        loop = asyncio.get_running_loop()
        return json_dumps_safe(await loop.run_in_executor(None, _run))

    return coordinator
