import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ToolsConfig } from "../../lib/toolsConfig";

const cards: {
  to: string;
  title: string;
  body: string;
}[] = [
  {
    to: "/tools/pead/single",
    title: "PEAD — single symbol",
    body: "Full orchestrated run: event study, layers, synthesis, optional files.",
  },
  {
    to: "/tools/pead/recent",
    title: "PEAD — recent announcements",
    body: "Batch the top N recent NSE announcements (CLI recent mode).",
  },
  {
    to: "/tools/scoring",
    title: "PEAD scoring stack",
    body: "src/scoring — CARs + five components + composite (no technicals/news/files).",
  },
  {
    to: "/tools/fundamentals",
    title: "Fundamentals",
    body: "src/fundamentals — screening ratios & pillar scores (Yahoo/NSE bundle).",
  },
  {
    to: "/tools/technical",
    title: "Technical analysis",
    body: "src/technical — PEAD window or explicit start/end; you choose (no auto fallbacks).",
  },
  {
    to: "/tools/news",
    title: "News + sentiment",
    body: "src/news — headlines + TextBlob / optional OpenAI pipeline.",
  },
  {
    to: "/tools/trade-readiness",
    title: "Trade readiness",
    body: "src/trade_context — execution-context score & pillars (light inputs).",
  },
  {
    to: "/tools/document-pdf",
    title: "Document PDF parse",
    body: "src/documents — parse an on-disk announcement PDF (expected naming).",
  },
  {
    to: "/tools/execution-snapshot",
    title: "Execution snapshot (combo)",
    body: "Technicals + trade readiness in one call — debugging convenience.",
  },
  {
    to: "/tools/yahoo-calendar",
    title: "Yahoo calendar snippet",
    body: "Best-effort calendar / earnings_dates from yfinance.",
  },
];

export default function ToolsHub() {
  const [config, setConfig] = useState<ToolsConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    void fetch("/api/tools/config")
      .then((r) => r.json())
      .then((d: ToolsConfig) => setConfig(d))
      .catch(() => setConfigError("Could not load /api/tools/config (is the API running?)"));
  }, []);

  return (
    <div className="min-h-screen bg-surface pb-24">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="text-xl font-semibold text-white">Research tools</h1>
        <p className="mt-1 text-sm text-slate-400">
          Each tool has its own page so you can reproduce and fix issues in isolation. Results are
          JSON; successful PEAD runs also write files under your output directory.
        </p>

        {configError && (
          <div className="mt-6 rounded-xl border border-amber-900/50 bg-amber-950/30 p-4 text-sm text-amber-100">
            {configError}
          </div>
        )}

        {config?.cli_equivalent && (
          <section className="mt-6 rounded-xl border border-surface-border bg-surface-raised/40 p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              CLI parity
            </h2>
            <p className="mt-2 font-mono text-xs text-slate-400">
              Modes: {config.cli_equivalent.modes?.join(", ")}
            </p>
            <ul className="mt-2 list-inside list-disc text-xs text-slate-500">
              {config.cli_equivalent.flags?.map((f) => (
                <li key={f} className="font-mono">
                  {f}
                </li>
              ))}
            </ul>
          </section>
        )}

        {config?.market_model && (
          <section className="mt-4 grid gap-3 rounded-xl border border-surface-border bg-black/20 p-4 text-sm text-slate-400 md:grid-cols-2">
            <div>
              <span className="text-slate-500">Market index</span>{" "}
              <code className="text-sky-300">{config.market_model.market_index}</code>
            </div>
            <div>
              <span className="text-slate-500">Estimation window</span>{" "}
              {config.market_model.estimation_window_days} trading days
            </div>
            <div>
              <span className="text-slate-500">Min trading days</span>{" "}
              {config.market_model.min_trading_days}
            </div>
            <div>
              <span className="text-slate-500">CAR windows</span>{" "}
              {(config.car_windows_days ?? []).join(", ")}d
            </div>
            <div>
              <span className="text-slate-500">Significance</span> α = {config.significance_level}
            </div>
            <div>
              <span className="text-slate-500">News LLM (sentiment layer)</span>{" "}
              <code className="text-xs text-slate-300">{config.news?.openai_news_model}</code>
            </div>
          </section>
        )}

        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {cards.map((c) => (
            <li key={c.to}>
              <Link
                to={c.to}
                className="block rounded-2xl border border-surface-border bg-surface-raised/30 p-5 transition hover:border-sky-500/40 hover:bg-surface-raised/50"
              >
                <h2 className="font-semibold text-white">{c.title}</h2>
                <p className="mt-2 text-sm text-slate-400">{c.body}</p>
                <span className="mt-3 inline-block text-sm text-sky-400">Open →</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
