import { useCallback, useEffect, useState } from "react";
import { ResultPanel } from "../../components/tools/ResultPanel";
import { ToolPageChrome } from "../../components/tools/ToolPageChrome";
import { formatApiError } from "../../lib/apiError";
import type { ToolsConfig } from "../../lib/toolsConfig";

type NewsCitationRow = {
  id: number;
  fetched_at: string;
  fetched_date: string;
  symbol: string;
  article_published_at: string | null;
  url: string;
  title: string;
  source: string | null;
  summary: string | null;
  body_excerpt: string | null;
  metadata: Record<string, unknown>;
  scrape_ok: boolean;
  scrape_error: string | null;
  polarity: number | null;
  stance: string | null;
};

function utcTodayYmd(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function NewsToolPage() {
  const [symbol, setSymbol] = useState("SMLMAH");
  const [lookbackDays, setLookbackDays] = useState(90);
  const [maxArticles, setMaxArticles] = useState(80);
  const [scrapeBodies, setScrapeBodies] = useState(true);
  const [maxScrape, setMaxScrape] = useState(25);
  const [endDate, setEndDate] = useState(""); // YYYY-MM-DD optional
  const [useCache, setUseCache] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [citationFilterDate, setCitationFilterDate] = useState(utcTodayYmd);
  const [citationSymbolOnly, setCitationSymbolOnly] = useState(true);
  const [citations, setCitations] = useState<NewsCitationRow[]>([]);
  const [citationsLoading, setCitationsLoading] = useState(false);
  const [citationsError, setCitationsError] = useState<string | null>(null);

  const loadCitations = useCallback(async () => {
    setCitationsLoading(true);
    setCitationsError(null);
    try {
      const params = new URLSearchParams({ date: citationFilterDate });
      if (citationSymbolOnly && symbol.trim()) {
        params.set("symbol", symbol.trim().toUpperCase());
      }
      const res = await fetch(`/api/news/articles?${params.toString()}`);
      const data = (await res.json()) as {
        articles?: NewsCitationRow[];
        count?: number;
        fetched_date_filter?: string;
      };
      if (!res.ok) throw new Error(formatApiError(data, res.statusText));
      setCitations(data.articles ?? []);
    } catch (e) {
      setCitationsError(e instanceof Error ? e.message : String(e));
      setCitations([]);
    } finally {
      setCitationsLoading(false);
    }
  }, [citationFilterDate, citationSymbolOnly, symbol]);

  useEffect(() => {
    void fetch("/api/tools/config")
      .then((r) => r.json())
      .then((d: ToolsConfig) => {
        if (d.news?.lookback_days_default != null) setLookbackDays(d.news.lookback_days_default);
        if (d.news?.max_articles_default != null) setMaxArticles(d.news.max_articles_default);
        if (d.news?.max_scrape_default != null) setMaxScrape(d.news.max_scrape_default);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    void loadCitations();
  }, [loadCitations]);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/tools/run/news", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol.trim().toUpperCase(),
          lookback_days: lookbackDays,
          max_articles: maxArticles,
          use_cache: useCache,
          scrape_bodies: scrapeBodies,
          max_scrape: maxScrape,
          ...(endDate.trim() ? { end_date: endDate.trim() } : {}),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(formatApiError(data, res.statusText));
      setResult(data);
      void loadCitations();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ToolPageChrome
      title="News + sentiment"
      description="Yahoo + Google RSS in a date window; optional article body scrape (trafilatura); TextBlob + optional OpenAI; aggregate bullish/bearish/neutral label. Research only."
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
          <span className="text-slate-400">End date (optional, YYYY-MM-DD)</span>
          <input
            type="date"
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <span className="text-xs text-slate-600">Leave empty for “now”. Window = end − lookback.</span>
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Lookback (days)</span>
            <input
              type="number"
              min={1}
              max={730}
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={lookbackDays}
              onChange={(e) => setLookbackDays(Number(e.target.value))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Max articles</span>
            <input
              type="number"
              min={1}
              max={500}
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={maxArticles}
              onChange={(e) => setMaxArticles(Number(e.target.value))}
            />
          </label>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Max articles to scrape (full text)</span>
            <input
              type="number"
              min={0}
              max={80}
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={maxScrape}
              onChange={(e) => setMaxScrape(Number(e.target.value))}
            />
            <span className="text-xs text-slate-600">0 = headlines/snippets only (faster).</span>
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={scrapeBodies}
            onChange={(e) => setScrapeBodies(e.target.checked)}
          />
          Scrape article pages for body text + metadata (first N URLs)
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={useCache}
            onChange={(e) => setUseCache(e.target.checked)}
          />
          Use data cache (company name lookup)
        </label>
        <button
          type="button"
          disabled={loading || !symbol.trim()}
          onClick={() => void run()}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-300 disabled:opacity-40"
        >
          {loading ? "Running…" : "Run news layer"}
        </button>
      </div>
      <ResultPanel error={error} result={result} loading={loading} />

      <div className="mt-10 space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">Stored citations (SQLite)</h2>
        <p className="text-sm text-slate-500">
          Each run persists articles to the DB. Filter by <strong className="text-slate-400">fetch date (UTC)</strong> — use
          today&apos;s UTC date to see everything scraped in this calendar day.
        </p>
        <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-surface-border bg-surface-raised/20 p-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-400">Fetch date (UTC)</span>
            <input
              type="date"
              className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-slate-100"
              value={citationFilterDate}
              onChange={(e) => setCitationFilterDate(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={citationSymbolOnly}
              onChange={(e) => setCitationSymbolOnly(e.target.checked)}
            />
            Only this symbol
          </label>
          <button
            type="button"
            onClick={() => void loadCitations()}
            className="rounded-lg border border-surface-border px-4 py-2 text-sm text-slate-200 hover:bg-surface-raised"
          >
            Refresh list
          </button>
        </div>

        {citationsError ? (
          <p className="text-sm text-rose-400">{citationsError}</p>
        ) : null}
        {citationsLoading ? (
          <p className="text-sm text-slate-500">Loading citations…</p>
        ) : citations.length === 0 ? (
          <p className="text-sm text-slate-500">No rows for this filter.</p>
        ) : (
          <ol className="space-y-4">
            {citations.map((c, idx) => (
              <li
                key={c.id}
                className="rounded-xl border border-surface-border bg-surface-raised/40 p-4 text-sm text-slate-200"
              >
                <div className="mb-2 flex flex-wrap items-baseline gap-2">
                  <span className="font-mono text-xs text-sky-400">[{idx + 1}]</span>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-sky-300 hover:underline"
                  >
                    {c.title}
                  </a>
                  <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-400">
                    {c.symbol}
                  </span>
                  {c.stance ? (
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        c.stance === "bullish"
                          ? "bg-emerald-950/80 text-emerald-200"
                          : c.stance === "bearish"
                            ? "bg-rose-950/80 text-rose-200"
                            : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {c.stance}
                    </span>
                  ) : null}
                </div>
                <div className="space-y-1 text-xs text-slate-500">
                  <p>
                    <span className="text-slate-600">Citation:</span> {c.title} —{" "}
                    <span className="break-all text-slate-500">{c.url}</span>
                  </p>
                  <p>
                    Fetched (UTC): {c.fetched_at}
                    {c.article_published_at ? (
                      <> · Article date: {c.article_published_at}</>
                    ) : null}
                    {c.source ? <> · {c.source}</> : null}
                    {c.polarity != null ? <> · polarity {c.polarity.toFixed(3)}</> : null}
                  </p>
                  {(c.metadata?.hostname as string) || (c.metadata?.sitename as string) ? (
                    <p>
                      Site:{" "}
                      {String(c.metadata.hostname ?? c.metadata.sitename ?? "")}
                      {c.metadata.author ? <> · Author: {String(c.metadata.author)}</> : null}
                    </p>
                  ) : null}
                  {c.scrape_error ? (
                    <p className="text-amber-200/90">Scrape: {c.scrape_error}</p>
                  ) : null}
                  {c.body_excerpt ? (
                    <p className="mt-2 line-clamp-4 text-slate-400">{c.body_excerpt}</p>
                  ) : c.summary ? (
                    <p className="mt-2 line-clamp-3 text-slate-400">{c.summary}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </ToolPageChrome>
  );
}
