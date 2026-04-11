import { useState } from "react";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";

export default function YahooCalendarToolPage() {
  const [symbol, setSymbol] = useState("SMLMAH");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/tools/run/yahoo-calendar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(formatApiError(data, res.statusText));
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ToolPageChrome
      title="Yahoo calendar snippet"
      description="Best-effort calendar and earnings_dates from Yahoo Finance (yfinance). Empty fields usually mean Yahoo had no structured data for this ticker."
    >
      <div className="mt-6 space-y-4 rounded-2xl border border-surface-border bg-surface-raised/30 p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Symbol (NSE, without .NS)</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono uppercase text-slate-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={loading || !symbol.trim()}
          onClick={() => void run()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Fetching…" : "Fetch Yahoo snippet"}
        </button>
      </div>

      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
