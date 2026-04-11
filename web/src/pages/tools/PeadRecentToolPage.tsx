import { useEffect, useState } from "react";
import { PeadSharedOptions } from "../../components/tools/PeadSharedOptions";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";
import type { ToolsConfig } from "../../lib/toolsConfig";

export default function PeadRecentToolPage() {
  const [config, setConfig] = useState<ToolsConfig | null>(null);
  const [topN, setTopN] = useState(10);
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

  const runRecent = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        top_n: topN,
        visualize,
        use_cache: useCache,
        include_news: includeNews,
        output_dir: outputDir || undefined,
      };
      if (newsLookback !== "") body.news_lookback_days = Number(newsLookback);
      if (newsMaxArticles !== "") body.news_max_articles = Number(newsMaxArticles);

      const res = await fetch("/api/tools/run/recent", {
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
      title="PEAD — recent announcements"
      description="Analyze the top N recent NSE announcements (CLI recent mode). Results are summary rows — open PEAD single-symbol for full technical, fundamental, and news layers. Batch-from-CSV is not exposed here; use the CLI."
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
        <label className="flex max-w-xs flex-col gap-1 text-sm">
          <span className="text-slate-400">Top N announcements</span>
          <input
            type="number"
            min={1}
            max={100}
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
          />
          <span className="text-xs text-slate-600">Same as --top</span>
        </label>
        <button
          type="button"
          disabled={loading}
          onClick={() => void runRecent()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Running…" : "Run recent batch"}
        </button>
      </div>

      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
