import { useEffect, useState } from "react";
import { DateYmdInput, isValidYmd } from "../../components/tools/DateYmdInput";
import { PeadSharedOptions } from "../../components/tools/PeadSharedOptions";
import { PeadSingleResultView } from "../../components/tools/PeadSingleResultView";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";
import type { ToolsConfig } from "../../lib/toolsConfig";
import {
  EquityPipelineStagePicker,
  buildPipelineStagesBody,
  defaultStageTogglesAllOn,
  type StageToggleMap,
} from "../../components/tools/EquityPipelineStagePicker";

function defaultUtcRange(days: number): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - days);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

export default function PeadSingleToolPage() {
  const def = defaultUtcRange(180);
  const [config, setConfig] = useState<ToolsConfig | null>(null);
  const [symbol, setSymbol] = useState("SMLMAH");
  const [rangeStart, setRangeStart] = useState(def.start);
  const [rangeEnd, setRangeEnd] = useState(def.end);
  const [useCache, setUseCache] = useState(true);
  const [newsMaxArticles, setNewsMaxArticles] = useState<number | "">("");
  const [outputDir, setOutputDir] = useState("");
  const [stageToggles, setStageToggles] = useState<StageToggleMap>(defaultStageTogglesAllOn);
  const [includeSymbolNewsAiDigest, setIncludeSymbolNewsAiDigest] = useState(true);
  const [includeMarketNewsAiDigest, setIncludeMarketNewsAiDigest] = useState(true);
  const [technicalIncludeAiVerdict, setTechnicalIncludeAiVerdict] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  useEffect(() => {
    void fetch("/api/tools/config")
      .then((r) => r.json())
      .then((d: ToolsConfig) => {
        setConfig(d);
        if (d.paths?.output_default) setOutputDir(d.paths.output_default);
        if (d.news?.max_articles_default != null)
          setNewsMaxArticles(d.news.max_articles_default);
      })
      .catch(() => setError("Could not load /api/tools/config (is the API running?)"));
  }, []);

  const hasAnyPipelineStage = Object.values(stageToggles).some(Boolean);
  const canSubmit =
    Boolean(symbol.trim()) &&
    isValidYmd(rangeStart.trim()) &&
    isValidYmd(rangeEnd.trim()) &&
    hasAnyPipelineStage;

  const runSingle = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        symbol: symbol.trim().toUpperCase(),
        range_start: rangeStart.trim(),
        range_end: rangeEnd.trim(),
        use_cache: useCache,
        include_news: stageToggles.run_news_tool,
        include_desk_insight: stageToggles.run_research_desk,
        include_market_sentiment: stageToggles.run_market_sentiment_tool,
        include_symbol_news_ai_digest: includeSymbolNewsAiDigest,
        include_market_news_ai_digest: includeMarketNewsAiDigest,
        technical_include_ai_verdict: technicalIncludeAiVerdict,
        output_dir: outputDir || undefined,
      };
      if (newsMaxArticles !== "") body.news_max_articles = Number(newsMaxArticles);
      Object.assign(body, buildPipelineStagesBody(stageToggles));

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
      title="Equity research — single symbol"
      description="One window (range start → end): shared OHLCV, technical (same chart payload as the Technical tool), symbol news + optional broader market-context headlines in that window, then trade context on the same prices. Fundamentals are a company snapshot, not day-by-day over the range."
    >
      <PeadSharedOptions
        config={config}
        outputDir={outputDir}
        setOutputDir={setOutputDir}
        useCache={useCache}
        setUseCache={setUseCache}
        newsMaxArticles={newsMaxArticles}
        setNewsMaxArticles={setNewsMaxArticles}
        newsWindowFromAnalysisRange={{ start: rangeStart, end: rangeEnd }}
      />

      <div className="mt-6">
        <EquityPipelineStagePicker toggles={stageToggles} onChange={setStageToggles} />
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-400">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={includeSymbolNewsAiDigest}
            onChange={(e) => setIncludeSymbolNewsAiDigest(e.target.checked)}
            className="rounded border-surface-border"
          />
          Symbol news: OpenAI <span className="font-mono text-slate-500">ai_digest</span>
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={includeMarketNewsAiDigest}
            onChange={(e) => setIncludeMarketNewsAiDigest(e.target.checked)}
            className="rounded border-surface-border"
          />
          Market sentiment: OpenAI <span className="font-mono text-slate-500">ai_digest</span>
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={technicalIncludeAiVerdict}
            onChange={(e) => setTechnicalIncludeAiVerdict(e.target.checked)}
            className="rounded border-surface-border"
          />
          After technicals: AI trade plan (S/R, entry & exit levels)
        </label>
      </div>

      <div className="mt-6 space-y-4 rounded-2xl border border-surface-border bg-surface-raised/20 p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Symbol (NSE)</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono uppercase text-slate-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Analysis range start (YYYY-MM-DD)</span>
            <DateYmdInput
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={rangeStart}
              onChange={setRangeStart}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Analysis range end (YYYY-MM-DD)</span>
            <DateYmdInput
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={rangeEnd}
              onChange={setRangeEnd}
              min={rangeStart.trim() || undefined}
            />
          </label>
        </div>
        {!hasAnyPipelineStage ? (
          <p className="text-xs text-amber-200/90">Select at least one pipeline stage above.</p>
        ) : null}
        <button
          type="button"
          disabled={loading || !canSubmit}
          onClick={() => void runSingle()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Running…" : "Run equity research"}
        </button>
      </div>

      {result !== null && !loading && <PeadSingleResultView payload={result} />}
      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
