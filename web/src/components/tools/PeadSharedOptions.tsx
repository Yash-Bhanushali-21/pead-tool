import { formatYmdOnly } from "../../lib/formatYmd";
import type { ToolsConfig } from "../../lib/toolsConfig";

type Props = {
  config: ToolsConfig | null;
  outputDir: string;
  setOutputDir: (v: string) => void;
  useCache: boolean;
  setUseCache: (v: boolean) => void;
  /** Rolling window from end-date (recent-announcements tool). Omit for equity single (range-driven news). */
  newsLookback?: number | "";
  setNewsLookback?: (v: number | "") => void;
  newsMaxArticles: number | "";
  setNewsMaxArticles: (v: number | "") => void;
  /** When set, news dates follow this range; lookback UI is hidden. */
  newsWindowFromAnalysisRange?: { start: string; end: string };
};

export function PeadSharedOptions({
  config,
  outputDir,
  setOutputDir,
  useCache,
  setUseCache,
  newsLookback,
  setNewsLookback,
  newsMaxArticles,
  setNewsMaxArticles,
  newsWindowFromAnalysisRange,
}: Props) {
  const useLookback = Boolean(setNewsLookback) && newsWindowFromAnalysisRange == null;
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
              checked={useCache}
              onChange={(e) => setUseCache(e.target.checked)}
            />
            Use data cache (uncheck = <code className="text-xs">--no-cache</code>)
          </label>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {useLookback ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">News lookback (days)</span>
            <input
              type="number"
              min={1}
              max={730}
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={newsLookback ?? ""}
              onChange={(e) =>
                setNewsLookback?.(e.target.value === "" ? "" : Number(e.target.value))
              }
              placeholder={String(config?.news?.lookback_days_default ?? 90)}
            />
            <span className="text-xs text-slate-600">Maps to --news-days</span>
          </label>
        ) : (
          <div className="flex flex-col gap-1 rounded-lg border border-surface-border bg-surface/40 px-3 py-2 text-sm">
            <span className="text-slate-400">News date window</span>
            {newsWindowFromAnalysisRange ? (
              <>
                <p className="text-slate-300">
                  Headlines are filtered to your <strong className="font-medium text-slate-200">analysis range</strong>{" "}
                  (inclusive):
                </p>
                <p className="font-mono text-xs text-sky-200/90">
                  {formatYmdOnly(newsWindowFromAnalysisRange.start)} →{" "}
                  {formatYmdOnly(newsWindowFromAnalysisRange.end)}
                </p>
                <p className="text-xs text-slate-600">Lookback days do not apply on this tool.</p>
              </>
            ) : (
              <p className="text-xs text-slate-600">News window is set by the tool (not lookback days).</p>
            )}
          </div>
        )}
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
          {newsWindowFromAnalysisRange ? (
            <span className="text-xs text-slate-600">
              Max items collected within the range above (newest first within the cap).
            </span>
          ) : null}
        </label>
      </div>
    </div>
  );
}
