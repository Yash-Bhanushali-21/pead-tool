import { useState } from "react";
import {
  TechnicalAnalysisChart,
  type TechnicalChartPayload,
} from "../../components/tools/TechnicalAnalysisChart";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";
import {
  isResearchVerdict,
  TechnicalVerdictPanel,
} from "../../components/tools/TechnicalVerdictPanel";

function technicalChartFromResult(data: unknown): TechnicalChartPayload | null {
  if (!data || typeof data !== "object") return null;
  const ta = (data as { technical_analysis?: { chart?: unknown } }).technical_analysis;
  const ch = ta?.chart;
  if (!ch || typeof ch !== "object") return null;
  const c = ch as TechnicalChartPayload;
  if (!Array.isArray(c.bars) || c.bars.length === 0) return null;
  return c;
}

type PriceWindow = "pead_event" | "explicit_range";
type AnnouncementResolution = "auto" | "manual";

export default function TechnicalToolPage() {
  const [symbol, setSymbol] = useState("SMLMAH");
  const [useCache, setUseCache] = useState(true);
  const [priceWindow, setPriceWindow] = useState<PriceWindow>("pead_event");
  const [announcementResolution, setAnnouncementResolution] =
    useState<AnnouncementResolution>("auto");
  const [announcementDate, setAnnouncementDate] = useState("");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [includeChart, setIncludeChart] = useState(true);
  const [includeAiVerdict, setIncludeAiVerdict] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  const canSubmit = () => {
    if (!symbol.trim()) return false;
    if (priceWindow === "explicit_range") {
      return Boolean(rangeStart.trim() && rangeEnd.trim());
    }
    if (announcementResolution === "manual") {
      return Boolean(announcementDate.trim());
    }
    return true;
  };

  const run = async () => {
    if (!canSubmit()) {
      setError(
        priceWindow === "explicit_range"
          ? "Set both range start and end (YYYY-MM-DD)."
          : "Set announcement date, or switch announcement resolution to Auto.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        symbol: symbol.trim().toUpperCase(),
        use_cache: useCache,
        price_window: priceWindow,
        include_chart: includeChart,
        include_ai_verdict: includeAiVerdict,
      };
      if (priceWindow === "pead_event") {
        body.announcement_resolution = announcementResolution;
        if (announcementResolution === "manual" && announcementDate.trim()) {
          body.announcement_date = announcementDate.trim();
        }
      } else {
        body.range_start = rangeStart.trim();
        body.range_end = rangeEnd.trim();
      }
      const res = await fetch("/api/tools/run/technical", {
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

  const chartPayload = result !== null ? technicalChartFromResult(result) : null;
  const verdictRaw =
    result !== null &&
    typeof result === "object" &&
    "research_verdict" in result
      ? (result as { research_verdict?: unknown }).research_verdict
      : null;
  const verdict = verdictRaw !== null && isResearchVerdict(verdictRaw) ? verdictRaw : null;

  return (
    <ToolPageChrome
      title="Technical analysis"
      description="src/technical — RSI, MACD, MAs, ATR%, pivot S/R. Choose the price window and optional chart payload; charts render below when included."
    >
      <div className="mt-6 space-y-5 rounded-2xl border border-surface-border bg-surface-raised/30 p-6">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-slate-400">Symbol (NSE)</span>
          <input
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 font-mono uppercase text-slate-100"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
        </label>

        <fieldset className="space-y-2">
          <legend className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Price window
          </legend>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-300">
            <input
              type="radio"
              name="pw"
              className="mt-1"
              checked={priceWindow === "pead_event"}
              onChange={() => setPriceWindow("pead_event")}
            />
            <span>
              <span className="font-medium text-slate-200">PEAD event window</span>
              <span className="mt-0.5 block text-xs text-slate-500">
                Same pre/post calendar span as the full PEAD pipeline around an announcement.
              </span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-300">
            <input
              type="radio"
              name="pw"
              className="mt-1"
              checked={priceWindow === "explicit_range"}
              onChange={() => setPriceWindow("explicit_range")}
            />
            <span>
              <span className="font-medium text-slate-200">Explicit date range</span>
              <span className="mt-0.5 block text-xs text-slate-500">
                Fetch OHLCV from NSE/Yahoo between two calendar dates you set (inclusive).
              </span>
            </span>
          </label>
        </fieldset>

        {priceWindow === "pead_event" && (
          <fieldset className="space-y-3 border-l-2 border-sky-900/50 pl-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Announcement date
            </legend>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
              <input
                type="radio"
                name="ar"
                checked={announcementResolution === "auto"}
                onChange={() => setAnnouncementResolution("auto")}
              />
              Auto — resolve latest earnings-style date from feeds (same as PEAD when date omitted)
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
              <input
                type="radio"
                name="ar"
                checked={announcementResolution === "manual"}
                onChange={() => setAnnouncementResolution("manual")}
              />
              Manual — you provide the anchor date
            </label>
            {announcementResolution === "manual" && (
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-slate-400">Announcement date (YYYY-MM-DD)</span>
                <input
                  type="date"
                  className="max-w-xs rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
                  value={announcementDate}
                  onChange={(e) => setAnnouncementDate(e.target.value)}
                />
              </label>
            )}
          </fieldset>
        )}

        {priceWindow === "explicit_range" && (
          <div className="grid gap-4 border-l-2 border-emerald-900/40 pl-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-400">Range start</span>
              <input
                type="date"
                className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
                value={rangeStart}
                onChange={(e) => setRangeStart(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-400">Range end</span>
              <input
                type="date"
                className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
                value={rangeEnd}
                onChange={(e) => setRangeEnd(e.target.value)}
              />
            </label>
          </div>
        )}

        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={useCache}
            onChange={(e) => setUseCache(e.target.checked)}
          />
          Use data cache
        </label>
        <label className="flex items-start gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            className="mt-1"
            checked={includeChart}
            onChange={(e) => setIncludeChart(e.target.checked)}
          />
          <span>
            Include chart payload (OHLCV + MAs, RSI, MACD, pivot S/R) — larger JSON response
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            className="mt-1"
            checked={includeAiVerdict}
            onChange={(e) => setIncludeAiVerdict(e.target.checked)}
          />
          <span>
            Include AI research verdict (entry/exit framing; requires{" "}
            <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-xs">OPENAI_API_KEY</code>{" "}
            on the server)
          </span>
        </label>

        <button
          type="button"
          disabled={loading || !canSubmit()}
          onClick={() => void run()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Running…" : "Run technical"}
        </button>
      </div>
      {chartPayload && <TechnicalAnalysisChart chart={chartPayload} />}
      {verdict && (
        <div className="mt-8">
          <TechnicalVerdictPanel verdict={verdict} />
        </div>
      )}
      <ResultPanel error={error} result={result} loading={loading} />
    </ToolPageChrome>
  );
}
