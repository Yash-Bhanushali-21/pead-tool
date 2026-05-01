export const EQUITY_PIPELINE_STAGE_IDS = [
  "fetch_price_window",
  "resolve_output_dir",
  "run_fundamentals_tool",
  "run_exchange_announcements",
  "run_technical_tool",
  "run_news_tool",
  "run_market_sentiment_tool",
  "run_trade_context",
  "run_research_desk",
] as const;

export type EquityPipelineStageId = (typeof EQUITY_PIPELINE_STAGE_IDS)[number];

export const EQUITY_PIPELINE_STAGE_LABELS: Record<
  EquityPipelineStageId,
  { title: string; hint: string }
> = {
  fetch_price_window: {
    title: "OHLCV fetch",
    hint: "Load daily price data for the analysis window (auto-added when required by other stages).",
  },
  resolve_output_dir: {
    title: "Output directory",
    hint: "Create timestamped run folder and write per-stage artefacts to disk.",
  },
  run_fundamentals_tool: {
    title: "Fundamentals",
    hint: "Company snapshot: valuation ratios, growth, margins, pillar scores (not day-by-day).",
  },
  run_exchange_announcements: {
    title: "Exchange announcements",
    hint: "NSE/BSE corporate filings: board meetings, results, corporate actions, regulatory notices.",
  },
  run_technical_tool: {
    title: "Technical analysis",
    hint: "RSI, MACD, Bollinger Bands, MAs, ATR, S/R pivots — same price window as OHLCV fetch.",
  },
  run_news_tool: {
    title: "Symbol news & sentiment",
    hint: "Headlines for this symbol: event classification, source-credibility scoring, news signals.",
  },
  run_market_sentiment_tool: {
    title: "Market context sentiment",
    hint: "Broader India/Nifty/sector headlines in the same window (macro context, not stock-specific).",
  },
  run_trade_context: {
    title: "Trade context",
    hint: "Trade readiness pillars: liquidity, volatility regime, indicator alignment, model fit.",
  },
  run_research_desk: {
    title: "Research desk (LLM)",
    hint: "Single OpenAI pass over the consolidated bundle — narrative synthesis (requires API key).",
  },
};
