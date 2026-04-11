import type { ToolsConfig } from "../../lib/toolsConfig";

type Props = {
  config: ToolsConfig | null;
  outputDir: string;
  setOutputDir: (v: string) => void;
  visualize: boolean;
  setVisualize: (v: boolean) => void;
  useCache: boolean;
  setUseCache: (v: boolean) => void;
  includeNews: boolean;
  setIncludeNews: (v: boolean) => void;
  newsLookback: number | "";
  setNewsLookback: (v: number | "") => void;
  newsMaxArticles: number | "";
  setNewsMaxArticles: (v: number | "") => void;
};

export function PeadSharedOptions({
  config,
  outputDir,
  setOutputDir,
  visualize,
  setVisualize,
  useCache,
  setUseCache,
  includeNews,
  setIncludeNews,
  newsLookback,
  setNewsLookback,
  newsMaxArticles,
  setNewsMaxArticles,
}: Props) {
  return (
    <div className="space-y-6 rounded-2xl border border-surface-border bg-surface-raised/30 p-6">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Output directory</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono text-sm text-slate-100"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="./output"
          />
        </label>
        <div className="flex flex-col gap-2 text-sm">
          <span className="text-slate-400">Toggles</span>
          <label className="flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={visualize}
              onChange={(e) => setVisualize(e.target.checked)}
            />
            Generate charts (same as CLI without <code className="text-xs">--no-visualize</code>)
          </label>
          <label className="flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={useCache}
              onChange={(e) => setUseCache(e.target.checked)}
            />
            Use data cache (uncheck = <code className="text-xs">--no-cache</code>)
          </label>
          <label className="flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={includeNews}
              onChange={(e) => setIncludeNews(e.target.checked)}
            />
            Include news + sentiment (uncheck = <code className="text-xs">--no-news</code>)
          </label>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">News lookback (days)</span>
          <input
            type="number"
            min={1}
            max={730}
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={newsLookback}
            onChange={(e) =>
              setNewsLookback(e.target.value === "" ? "" : Number(e.target.value))
            }
            placeholder={String(config?.news?.lookback_days_default ?? 90)}
          />
          <span className="text-xs text-slate-600">Maps to --news-days</span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Max news articles (cap)</span>
          <input
            type="number"
            min={1}
            max={500}
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={newsMaxArticles}
            onChange={(e) =>
              setNewsMaxArticles(e.target.value === "" ? "" : Number(e.target.value))
            }
            placeholder={String(config?.news?.max_articles_default ?? 80)}
          />
        </label>
      </div>
    </div>
  );
}
