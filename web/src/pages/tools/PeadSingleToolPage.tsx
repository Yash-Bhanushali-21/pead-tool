import { useEffect, useState } from "react";
import { PeadSharedOptions } from "../../components/tools/PeadSharedOptions";
import { PeadSingleResultView } from "../../components/tools/PeadSingleResultView";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";
import type { ToolsConfig } from "../../lib/toolsConfig";

export default function PeadSingleToolPage() {
  const [config, setConfig] = useState<ToolsConfig | null>(null);
  const [symbol, setSymbol] = useState("SMLMAH");
  const [announcementDate, setAnnouncementDate] = useState("");
  const [visualize, setVisualize] = useState(true);
  const [useCache, setUseCache] = useState(true);
  const [includeNews, setIncludeNews] = useState(true);
  const [newsLookback, setNewsLookback] = useState<number | "">("");
  const [newsMaxArticles, setNewsMaxArticles] = useState<number | "">("");
  const [outputDir, setOutputDir] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  useEffect(() => {
    void fetch("/api/tools/config")
      .then((r) => r.json())
      .then((d: ToolsConfig) => {
        setConfig(d);
        if (d.paths?.output_default) setOutputDir(d.paths.output_default);
        if (d.news?.lookback_days_default != null) setNewsLookback(d.news.lookback_days_default);
        if (d.news?.max_articles_default != null)
          setNewsMaxArticles(d.news.max_articles_default);
      })
      .catch(() => setError("Could not load /api/tools/config (is the API running?)"));
  }, []);

  const runSingle = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        symbol: symbol.trim().toUpperCase(),
        visualize,
        use_cache: useCache,
        include_news: includeNews,
        output_dir: outputDir || undefined,
      };
      if (announcementDate.trim()) body.announcement_date = announcementDate.trim();
      if (newsLookback !== "") body.news_lookback_days = Number(newsLookback);
      if (newsMaxArticles !== "") body.news_max_articles = Number(newsMaxArticles);

      const res = await fetch("/api/tools/run/single", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
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
      title="PEAD — single symbol"
      description="Full PEAD pipeline for one NSE symbol. Same filters as CLI single mode."
    >
      <PeadSharedOptions
        config={config}
        outputDir={outputDir}
        setOutputDir={setOutputDir}
        visualize={visualize}
        setVisualize={setVisualize}
        useCache={useCache}
        setUseCache={setUseCache}
        includeNews={includeNews}
        setIncludeNews={setIncludeNews}
        newsLookback={newsLookback}
        setNewsLookback={setNewsLookback}
        newsMaxArticles={newsMaxArticles}
        setNewsMaxArticles={setNewsMaxArticles}
      />

      <div className="mt-6 space-y-4 rounded-2xl border border-surface-border bg-surface-raised/20 p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Symbol (NSE)</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono uppercase text-slate-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">
            Announcement date (optional — leave empty to auto-detect)
          </span>
          <input
            type="date"
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={announcementDate}
            onChange={(e) => setAnnouncementDate(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={loading || !symbol.trim()}
          onClick={() => void runSingle()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Running…" : "Run single analysis"}
        </button>
      </div>

      {result !== null && <PeadSingleResultView payload={result} />}
      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
