import { useState } from "react";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";

export default function DocumentPdfToolPage() {
  const [symbol, setSymbol] = useState("SMLMAH");
  const [announcementDate, setAnnouncementDate] = useState("");
  const [useCache, setUseCache] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  const run = async () => {
    if (!announcementDate.trim()) {
      setError("Announcement date is required (PDF filename uses YYYYMMDD).");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/tools/run/document-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol.trim().toUpperCase(),
          announcement_date: announcementDate.trim(),
          use_cache: useCache,
        }),
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
      title="Document PDF parse"
      description="src/documents — parse a PDF already saved as {SYMBOL}_{YYYYMMDD}.pdf under the server PDF download directory (no NSE fetch from this endpoint)."
    >
      <div className="mt-6 space-y-4 rounded-2xl border border-surface-border bg-surface-raised/30 p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Symbol (NSE)</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono uppercase text-slate-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Announcement date</span>
          <input
            type="date"
            required
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={announcementDate}
            onChange={(e) => setAnnouncementDate(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={useCache}
            onChange={(e) => setUseCache(e.target.checked)}
          />
          Use cache flag (analyzer init)
        </label>
        <button
          type="button"
          disabled={loading || !symbol.trim() || !announcementDate.trim()}
          onClick={() => void run()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Parsing…" : "Parse PDF"}
        </button>
      </div>
      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
