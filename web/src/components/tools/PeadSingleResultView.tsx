import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { formatYmdOnly } from "../../lib/formatYmd";
import { TechnicalAnalysisChart } from "./TechnicalAnalysisChart";
import type { TechnicalChartPayload } from "./technicalChartTypes";

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function technicalChartFromInner(inner: Record<string, unknown>): TechnicalChartPayload | null {
  const ta = inner.technical_analysis;
  if (!isRecord(ta)) return null;
  const ch = ta.chart;
  if (!isRecord(ch)) return null;
  const c = ch as TechnicalChartPayload;
  if (!Array.isArray(c.bars) || c.bars.length === 0) return null;
  return c;
}

function numFmt(v: unknown, digits = 2): string {
  if (typeof v === "number" && Number.isFinite(v)) return v.toFixed(digits);
  if (v === null || v === undefined) return "—";
  return String(v);
}

export function CollapsibleToolSection({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-xl border border-surface-border bg-surface-raised/25">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-semibold text-slate-200"
      >
        <span>{title}</span>
        <span className="text-xs font-normal text-slate-500">{open ? "Hide" : "Show"}</span>
      </button>
      {open && <div className="border-t border-surface-border px-4 pb-4 pt-1">{children}</div>}
    </section>
  );
}

function MetricGrid({ items }: { items: { label: string; value: string }[] }) {
  return (
    <dl className="mt-2 grid gap-2 sm:grid-cols-2">
      {items.map((row) => (
        <div
          key={row.label}
          className="flex flex-col gap-0.5 rounded-lg bg-black/20 px-3 py-2 text-xs"
        >
          <dt className="text-slate-500">{row.label}</dt>
          <dd className="font-mono text-slate-200">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function ScoreBar({
  label,
  value,
  max = 100,
}: {
  label: string;
  value: number | null | undefined;
  /** Bar width denominator (e.g. 25 for fundamental pillars). */
  max?: number;
}) {
  const v =
    typeof value === "number" && Number.isFinite(value)
      ? Math.max(0, Math.min(max, value))
      : null;
  const pct = v !== null ? (v / max) * 100 : 0;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="font-mono text-slate-200">
          {v !== null ? (max === 100 ? v.toFixed(1) : `${v.toFixed(1)} / ${max}`) : "—"}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        {v !== null && (
          <div
            className="h-full rounded-full bg-sky-500/80"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}

export function TechnicalSection({
  ta,
  toolError,
  toolMeta,
}: {
  ta: Record<string, unknown> | undefined;
  toolError?: string;
  toolMeta?: Record<string, unknown>;
}) {
  if (!ta || Object.keys(ta).length === 0) {
    return (
      <div className="space-y-3 text-sm">
        {toolMeta && Object.keys(toolMeta).length > 0 && (
          <div className="rounded-lg border border-surface-border bg-black/25 px-3 py-2 text-xs text-slate-400">
            <p className="font-medium text-slate-500">Technical tool (same as /api/tools/run/technical)</p>
            <MetricGrid
              items={[
                { label: "Success", value: String(toolMeta.success ?? "—") },
                { label: "Price window", value: String(toolMeta.price_window ?? "—") },
                {
                  label: "OHLC from",
                  value: formatYmdOnly(toolMeta.ohlc_index_start as string | undefined),
                },
                {
                  label: "OHLC to",
                  value: formatYmdOnly(toolMeta.ohlc_index_end as string | undefined),
                },
              ]}
            />
          </div>
        )}
        {toolError ? (
          <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-amber-100">
            Technical tool error: {toolError}
          </p>
        ) : null}
        <p className="text-slate-500">No technical snapshot in this response.</p>
      </div>
    );
  }
  const scores = isRecord(ta.scores) ? ta.scores : {};
  const labels = isRecord(ta.labels) ? ta.labels : {};
  const last = isRecord(ta.last) ? ta.last : {};
  const notes = Array.isArray(ta.notes) ? ta.notes : [];

  return (
    <div className="space-y-3 text-sm text-slate-300">
      {toolMeta && Object.keys(toolMeta).length > 0 && (
        <div className="rounded-lg border border-surface-border bg-black/25 px-3 py-2 text-xs text-slate-400">
          <p className="font-medium text-slate-500">Technical tool (same as /api/tools/run/technical)</p>
          <MetricGrid
            items={[
              { label: "Success", value: String(toolMeta.success ?? "—") },
              { label: "Price window", value: String(toolMeta.price_window ?? "—") },
              {
                label: "OHLC from",
                value: formatYmdOnly(toolMeta.ohlc_index_start as string | undefined),
              },
              {
                label: "OHLC to",
                value: formatYmdOnly(toolMeta.ohlc_index_end as string | undefined),
              },
            ]}
          />
        </div>
      )}
      {typeof ta.stance === "string" && (
        <p className="leading-relaxed text-slate-200">{ta.stance}</p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <ScoreBar
          label="Technical score"
          value={typeof scores.technical_score === "number" ? scores.technical_score : null}
          max={100}
        />
        <ScoreBar
          label="Trend"
          value={typeof scores.trend === "number" ? scores.trend : null}
          max={100}
        />
        <ScoreBar
          label="Momentum"
          value={typeof scores.momentum === "number" ? scores.momentum : null}
          max={100}
        />
      </div>
      <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <span className="text-slate-500">Trend</span>{" "}
          <span className="text-slate-300">{String(labels.trend ?? "—")}</span>
        </div>
        <div>
          <span className="text-slate-500">Momentum</span>{" "}
          <span className="text-slate-300">{String(labels.momentum ?? "—")}</span>
        </div>
        <div>
          <span className="text-slate-500">Volatility</span>{" "}
          <span className="text-slate-300">{String(labels.volatility ?? "—")}</span>
        </div>
        <div>
          <span className="text-slate-500">Regime (ADX)</span>{" "}
          <span className="text-slate-300">{String(labels.trend_regime ?? "—")}</span>
        </div>
      </div>
      <MetricGrid
        items={[
          { label: "Close", value: numFmt(last.close) },
          { label: "RSI", value: numFmt(last.rsi, 1) },
          { label: "MACD hist", value: numFmt(last.macd_histogram, 4) },
          { label: "ATR %", value: last.atr_pct != null ? numFmt(Number(last.atr_pct) * 100, 2) + " %" : "—" },
          { label: "Vol vs 20d avg", value: numFmt(last.volume_vs_20d_avg, 2) },
          { label: "Sessions", value: String(ta.sessions_in_sample ?? "—") },
        ]}
      />
      {isRecord(last.advanced) ? (
        <div className="space-y-2 border-t border-surface-border pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Advanced indicators
          </p>
          <MetricGrid
            items={(() => {
              const adv = last.advanced as Record<string, unknown>;
              const rows: { label: string; value: string }[] = [
                { label: "ADX", value: numFmt(adv.adx, 2) },
                { label: "+DI / −DI", value: `${numFmt(adv.plus_di, 2)} / ${numFmt(adv.minus_di, 2)}` },
                {
                  label: "Supertrend (dir)",
                  value: `${numFmt(adv.supertrend, 4)} (${
                    adv.supertrend_direction === 1
                      ? "bull"
                      : adv.supertrend_direction === -1
                        ? "bear"
                        : "—"
                  })`,
                },
                { label: "Anchored VWAP", value: numFmt(adv.anchored_vwap, 4) },
                { label: "CMF", value: numFmt(adv.cmf, 4) },
                { label: "OBV Δ10", value: numFmt(adv.obv_change_10, 2) },
                { label: "BB width %", value: numFmt(adv.bb_bandwidth_pct, 2) },
                { label: "HV ann. %", value: numFmt(adv.hv_annualized_pct, 2) },
                {
                  label: "Squeeze",
                  value: adv.squeeze_on === true ? "On (BB inside KC)" : "Off",
                },
                {
                  label: "5-bar swing",
                  value: [
                    adv.local_high_last ? "local high" : null,
                    adv.local_low_last ? "local low" : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—",
                },
              ];
              const vb = adv.vs_benchmark;
              if (isRecord(vb) && typeof vb.benchmark_symbol === "string") {
                rows.push({
                  label: `vs ${vb.benchmark_symbol}`,
                  value:
                    typeof vb.rs_ratio_times_100 === "number"
                      ? `RS ${numFmt(vb.rs_ratio_times_100, 4)} · Δ${numFmt(vb.rs_ratio_change_lookback_pct, 2)}%`
                      : String(vb.error ?? "—"),
                });
              }
              return rows;
            })()}
          />
        </div>
      ) : null}
      {notes.length > 0 && (
        <ul className="list-inside list-disc text-xs text-slate-500">
          {notes.map((n, i) => (
            <li key={i}>{String(n)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const RATIO_LABELS: Record<string, string> = {
  pe_trailing: "P/E (trailing)",
  pe_forward: "P/E (forward)",
  peg: "PEG",
  price_to_book: "P/B",
  roe: "ROE",
  roa: "ROA",
  debt_to_equity: "Debt / equity",
  current_ratio: "Current ratio",
  operating_margin: "Operating margin",
  profit_margin: "Profit margin",
};

function FundamentalSection({ fa }: { fa: Record<string, unknown> | undefined }) {
  if (!fa || Object.keys(fa).length === 0) {
    return <p className="text-sm text-slate-500">No fundamental block in this response.</p>;
  }
  const scores = isRecord(fa.scores) ? fa.scores : {};
  const pillars = ["valuation", "quality", "balance_sheet", "growth"] as const;
  const headline = isRecord(fa.headline_ratios) ? fa.headline_ratios : null;

  return (
    <div className="space-y-3 text-sm text-slate-300">
      {typeof fa.stance === "string" && (
        <p className="leading-relaxed text-slate-200">{fa.stance}</p>
      )}
      <ScoreBar
        label="Fundamental score"
        value={typeof scores.fundamental_score === "number" ? scores.fundamental_score : null}
        max={100}
      />
      <div className="grid gap-2 sm:grid-cols-2">
        {pillars.map((p) => (
          <ScoreBar
            key={p}
            label={p.replace("_", " ")}
            value={typeof scores[p] === "number" ? (scores[p] as number) : null}
            max={25}
          />
        ))}
      </div>
      {headline && Object.keys(headline).length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500">Headline ratios (Yahoo)</p>
          <MetricGrid
            items={Object.entries(headline).map(([k, v]) => ({
              label: RATIO_LABELS[k] ?? k.replace(/_/g, " "),
              value:
                typeof v === "number"
                  ? k.includes("margin") || k === "roe" || k === "roa"
                    ? `${(v * 100).toFixed(2)}%`
                    : numFmt(v, 3)
                  : String(v),
            }))}
          />
        </div>
      )}
      <p className="text-xs text-slate-500">
        Pillars are scored 0–25 each (valuation, quality, balance sheet, growth). When an output
        directory is set, fundamentals text/JSON (and the pillar chart when enabled server-side) may
        be written there.
      </p>
    </div>
  );
}

function AiDigestBlock({ digest }: { digest: Record<string, unknown> }) {
  const rationale = digest.rationale;
  const rationaleLines = Array.isArray(rationale)
    ? rationale.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    : typeof rationale === "string" && rationale.trim()
      ? [rationale.trim()]
      : [];
  const keyPoints = Array.isArray(digest.key_points)
    ? digest.key_points.filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    : [];
  const tone =
    typeof digest.tone_alignment === "string" && digest.tone_alignment.trim()
      ? digest.tone_alignment.trim()
      : null;
  const lim =
    typeof digest.limitations === "string" && digest.limitations.trim()
      ? digest.limitations.trim()
      : null;
  const model = typeof digest.model === "string" ? digest.model : null;
  const disc =
    typeof digest.disclaimer === "string" && digest.disclaimer.trim()
      ? digest.disclaimer.trim()
      : null;

  if (
    rationaleLines.length === 0 &&
    keyPoints.length === 0 &&
    !tone &&
    !lim
  ) {
    return null;
  }

  return (
    <div className="rounded-lg border border-sky-900/35 bg-sky-950/20 p-3 text-xs text-slate-300">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-sky-400/90">
        AI digest (post-headline meta-analysis)
      </p>
      {model && (
        <p className="mt-1 font-mono text-[10px] text-slate-500">
          Model: {model}
        </p>
      )}
      {rationaleLines.length > 0 && (
        <div className="mt-2 space-y-1.5 text-slate-300">
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Rationale</p>
          <ol className="list-decimal space-y-1.5 pl-4 leading-relaxed">
            {rationaleLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ol>
        </div>
      )}
      {keyPoints.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Key points</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 leading-relaxed text-slate-300">
            {keyPoints.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </div>
      )}
      {tone && (
        <p className="mt-3 leading-relaxed text-slate-400">
          <span className="font-medium text-slate-500">Tone vs score: </span>
          {tone}
        </p>
      )}
      {lim && (
        <p className="mt-2 leading-relaxed text-slate-500">
          <span className="font-medium text-slate-600">Limits: </span>
          {lim}
        </p>
      )}
      {disc && <p className="mt-2 text-[10px] text-slate-600">{disc}</p>}
    </div>
  );
}

function NewsSection({
  ns,
  layer,
}: {
  ns: unknown;
  /** Optional envelope from `run_news_sentiment_layer` (same as /api/tools/run/news). */
  layer?: Record<string, unknown>;
}) {
  if (ns === null || ns === undefined) {
    return (
      <p className="text-sm text-slate-500">
        News and sentiment were not included (Symbol news pipeline stage off, or the run returned
        nothing).
      </p>
    );
  }
  if (!isRecord(ns)) {
    return <p className="text-sm text-slate-500">Unexpected news payload shape.</p>;
  }
  if (typeof ns.error === "string") {
    return (
      <p className="text-sm text-amber-200/90">
        News layer error: {ns.error}
      </p>
    );
  }

  const llm = ns.llm;
  const articlesFromLayer =
    typeof layer?.article_count === "number" ? layer.article_count : undefined;
  const windowEndRaw =
    layer && isRecord(layer.window) && typeof layer.window.end === "string"
      ? layer.window.end
      : null;
  const windowStartRaw =
    layer && isRecord(layer.window) && typeof layer.window.start === "string"
      ? layer.window.start
      : null;
  const windowEnd = windowEndRaw != null ? formatYmdOnly(windowEndRaw) : "—";
  const windowStart = windowStartRaw != null ? formatYmdOnly(windowStartRaw) : "—";
  const lookback =
    layer && isRecord(layer.window) && typeof layer.window.lookback_days === "number"
      ? String(layer.window.lookback_days)
      : "—";
  const preview = Array.isArray(layer?.articles_preview) ? layer.articles_preview : [];

  return (
    <div className="space-y-3 text-sm text-slate-300">
      {layer && (
        <div className="rounded-lg border border-surface-border bg-black/25 px-3 py-2 text-xs text-slate-400">
          <p className="font-medium text-slate-500">News tool (same as /api/tools/run/news)</p>
          <MetricGrid
            items={[
              { label: "Articles (layer)", value: String(articlesFromLayer ?? ns.article_count ?? "—") },
              { label: "Window start", value: windowStart },
              { label: "Window end", value: windowEnd },
              {
                label: "Lookback mode",
                value: lookback !== "—" ? `${lookback} d` : "Fixed analysis range",
              },
              {
                label: "Persisted citations",
                value: String(layer.persisted_citations ?? "—"),
              },
            ]}
          />
        </div>
      )}
      {preview.length > 0 && (
        <div className="rounded-lg border border-surface-border bg-black/20 px-3 py-2">
          <p className="text-xs font-medium text-slate-500">Articles used in this run</p>
          <ul className="mt-2 max-h-64 space-y-2 overflow-y-auto text-xs">
            {preview.map((row, i) => {
              if (!isRecord(row)) return null;
              const url = typeof row.url === "string" ? row.url : "";
              const title = typeof row.title === "string" && row.title.trim() ? row.title : url || "Article";
              const pubRaw = typeof row.published === "string" ? row.published : null;
              const pub = pubRaw != null ? formatYmdOnly(pubRaw) : null;
              const src = typeof row.source === "string" ? row.source : null;
              if (!url) {
                return (
                  <li key={i} className="text-slate-500">
                    {title}
                  </li>
                );
              }
              return (
                <li key={i} className="leading-snug">
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-sky-300 underline decoration-sky-700/60 underline-offset-2 hover:text-sky-200"
                  >
                    {title}
                  </a>
                  {(pub || src) && (
                    <span className="mt-0.5 block text-slate-500">
                      {[pub, src].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <ScoreBar
        label="News score"
        value={typeof ns.news_score_0_100 === "number" ? ns.news_score_0_100 : null}
        max={100}
      />
      <MetricGrid
        items={[
          { label: "Articles (sentiment)", value: String(ns.article_count ?? articlesFromLayer ?? "—") },
          { label: "Method", value: String(ns.method ?? "—") },
          { label: "Mean polarity", value: numFmt(ns.mean_polarity, 3) },
          { label: "Mean subjectivity", value: numFmt(ns.mean_subjectivity, 3) },
        ]}
      />
      {ns.openai_used === true && (
        <p className="text-xs text-slate-500">OpenAI synthesis was used where configured.</p>
      )}
      {llm != null && (
        <details className="rounded-lg border border-surface-border bg-black/20 p-3 text-xs">
          <summary className="cursor-pointer text-slate-400">LLM synthesis (raw)</summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-slate-400">
            {typeof llm === "string" ? llm : JSON.stringify(llm, null, 2)}
          </pre>
        </details>
      )}
      {isRecord(ns.ai_digest) && <AiDigestBlock digest={ns.ai_digest} />}
      {ns.ai_digest_skipped_by_request === true && (
        <p className="text-[10px] text-slate-600">
          AI digest was turned off for this run (request toggle). Headline lexicon / optional LLM synthesis
          above are unchanged.
        </p>
      )}
      {ns.ai_digest_used === false &&
        !isRecord(ns.ai_digest) &&
        ns.ai_digest_skipped_by_request !== true && (
        <p className="text-[10px] text-slate-600">
          AI digest skipped (no API key, disabled via config, or model error). Lexicon / synthesis above
          still apply when present.
        </p>
      )}
    </div>
  );
}

function MarketSentimentSection({
  ms,
  layer,
}: {
  ms: unknown;
  layer?: Record<string, unknown>;
}) {
  if (ms === null || ms === undefined) {
    return (
      <p className="text-sm text-slate-500">
        Market sentiment was not included (disabled for this run or pipeline returned nothing).
      </p>
    );
  }
  if (!isRecord(ms)) {
    return <p className="text-sm text-slate-500">Unexpected market sentiment payload shape.</p>;
  }
  if (typeof ms.error === "string") {
    return (
      <p className="text-sm text-amber-200/90">Market sentiment layer error: {ms.error}</p>
    );
  }
  const preview = Array.isArray(layer?.articles_preview) ? layer.articles_preview : [];
  const rationale =
    layer && typeof layer.rationale_markdown === "string" ? layer.rationale_markdown : "";

  return (
    <div className="space-y-3 text-sm text-slate-300">
      {layer && (
        <div className="rounded-lg border border-surface-border bg-black/25 px-3 py-2 text-xs text-slate-400">
          <p className="font-medium text-slate-500">Market context tool (India / tape headlines)</p>
          <MetricGrid
            items={[
              {
                label: "Articles (layer)",
                value: String(layer.article_count ?? ms.article_count ?? "—"),
              },
              {
                label: "Window start",
                value: formatYmdOnly(
                  isRecord(layer.window) && typeof layer.window.start === "string"
                    ? layer.window.start
                    : undefined,
                ),
              },
              {
                label: "Window end",
                value: formatYmdOnly(
                  isRecord(layer.window) && typeof layer.window.end === "string"
                    ? layer.window.end
                    : undefined,
                ),
              },
            ]}
          />
        </div>
      )}
      {rationale.trim().length > 0 && (
        <div className="prose prose-invert prose-sm max-w-none prose-p:text-slate-300 prose-strong:text-slate-200">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{rationale}</ReactMarkdown>
        </div>
      )}
      {preview.length > 0 && (
        <div className="rounded-lg border border-surface-border bg-black/20 px-3 py-2">
          <p className="text-xs font-medium text-slate-500">Articles used in this pass</p>
          <ul className="mt-2 max-h-64 space-y-2 overflow-y-auto text-xs">
            {preview.map((row, i) => {
              if (!isRecord(row)) return null;
              const url = typeof row.url === "string" ? row.url : "";
              const title =
                typeof row.title === "string" && row.title.trim() ? row.title : url || "Article";
              const pubRaw = typeof row.published === "string" ? row.published : null;
              const pub = pubRaw != null ? formatYmdOnly(pubRaw) : null;
              const src = typeof row.source === "string" ? row.source : null;
              if (!url) {
                return (
                  <li key={i} className="text-slate-500">
                    {title}
                  </li>
                );
              }
              return (
                <li key={i} className="leading-snug">
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-sky-300 underline decoration-sky-700/60 underline-offset-2 hover:text-sky-200"
                  >
                    {title}
                  </a>
                  {(pub || src) && (
                    <span className="mt-0.5 block text-slate-500">
                      {[pub, src].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <ScoreBar
        label="Market-context news score"
        value={typeof ms.news_score_0_100 === "number" ? ms.news_score_0_100 : null}
        max={100}
      />
      <MetricGrid
        items={[
          { label: "Articles (sentiment)", value: String(ms.article_count ?? "—") },
          { label: "Method", value: String(ms.method ?? "—") },
          { label: "Mean polarity", value: numFmt(ms.mean_polarity, 3) },
        ]}
      />
      <p className="text-xs text-slate-500">
        Broader RSS / web-discovery pass (not exhaustive; not a macro forecast). Same research-only
        limits as symbol news.
      </p>
      {isRecord(ms.ai_digest) && <AiDigestBlock digest={ms.ai_digest} />}
      {ms.ai_digest_skipped_by_request === true && (
        <p className="text-[10px] text-slate-600">
          Market pass AI digest was turned off for this run (request toggle).
        </p>
      )}
      {ms.ai_digest_used === false &&
        !isRecord(ms.ai_digest) &&
        ms.ai_digest_skipped_by_request !== true && (
        <p className="text-[10px] text-slate-600">
          AI digest skipped for market pass (no API key, disabled, or model error).
        </p>
      )}
    </div>
  );
}

function TechnicalAiVerdictSection({
  requested,
  verdict,
}: {
  requested: boolean | undefined;
  verdict: unknown;
}) {
  if (requested === false) {
    return (
      <p className="text-sm text-slate-500">
        Technical AI commentary was not requested for this run (toggle off). Raw indicators and scores
        are still in Technical analysis above.
      </p>
    );
  }
  if (requested !== true) {
    return (
      <p className="text-sm text-slate-500">
        No technical AI commentary flag on this payload (older API or technical stage skipped).
      </p>
    );
  }
  if (!isRecord(verdict)) {
    return (
      <p className="text-sm text-slate-500">
        No technical commentary block returned (technical step may have failed or produced no verdict).
      </p>
    );
  }
  if (verdict.skipped === true) {
    return (
      <p className="rounded-lg border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-sm text-amber-100/90">
        Technical commentary skipped:{" "}
        {typeof verdict.reason === "string" ? verdict.reason : "unavailable."}
      </p>
    );
  }
  if (typeof verdict.error === "string") {
    return (
      <p className="rounded-lg border border-rose-900/40 bg-rose-950/20 px-3 py-2 text-sm text-rose-100/90">
        Technical commentary error: {verdict.error}
      </p>
    );
  }
  const text = typeof verdict.text === "string" ? verdict.text.trim() : "";
  if (!text) {
    return <p className="text-sm text-slate-500">No commentary text returned.</p>;
  }
  return (
    <div className="space-y-2 text-sm">
      {typeof verdict.model === "string" && (
        <p className="text-xs text-slate-500">
          Model: <span className="font-mono text-slate-400">{verdict.model}</span>
        </p>
      )}
      <div className="prose prose-invert prose-sm prose-headings:scroll-mt-20 max-w-none prose-p:text-slate-300 prose-li:text-slate-300 prose-headings:text-slate-200">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </div>
      <p className="text-xs text-slate-500">
        Model-generated plan from the technical snapshot—confirm levels against live quotes; overnight news
        and fundamentals can override the read.
      </p>
    </div>
  );
}

function ResearchDeskSection({ desk }: { desk: unknown }) {
  if (!isRecord(desk)) {
    return <p className="text-sm text-slate-500">No research desk payload.</p>;
  }
  if (desk.skipped === true) {
    return (
      <p className="rounded-lg border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-sm text-amber-100/90">
        Research desk skipped:{" "}
        {typeof desk.reason === "string" ? desk.reason : "disabled or unavailable."}
      </p>
    );
  }
  if (typeof desk.error === "string") {
    return (
      <p className="rounded-lg border border-rose-900/40 bg-rose-950/20 px-3 py-2 text-sm text-rose-100/90">
        Research desk error: {desk.error}
      </p>
    );
  }
  if (typeof desk.markdown !== "string" || !desk.markdown.trim()) {
    return <p className="text-sm text-slate-500">No desk narrative returned.</p>;
  }
  return (
    <div className="space-y-2 text-sm">
      {typeof desk.model === "string" && (
        <p className="text-xs text-slate-500">
          Model: <span className="font-mono text-slate-400">{desk.model}</span>
        </p>
      )}
      <div className="prose prose-invert prose-sm prose-headings:scroll-mt-20 max-w-none prose-p:text-slate-300 prose-li:text-slate-300 prose-headings:text-slate-200">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{desk.markdown}</ReactMarkdown>
      </div>
      <p className="text-xs text-slate-500">
        Research commentary only — not investment advice. Cross-check before any decision.
      </p>
    </div>
  );
}

export function TradeContextSection({ tc }: { tc: unknown }) {
  if (!isRecord(tc) || Object.keys(tc).length === 0) {
    return (
      <p className="text-sm text-slate-500">No trade / execution context block in this response.</p>
    );
  }
  const complete = tc.readiness_complete === true;
  const missing = Array.isArray(tc.missing_pillars) ? tc.missing_pillars : [];
  return (
    <div className="space-y-2 text-sm text-slate-300">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={
            complete
              ? "rounded-full bg-emerald-950/50 px-2 py-0.5 text-emerald-200"
              : "rounded-full bg-slate-800 px-2 py-0.5 text-slate-400"
          }
        >
          {complete ? "Readiness complete" : "Readiness incomplete"}
        </span>
        {!complete && missing.length > 0 && (
          <span className="text-slate-500">
            Missing pillars: {missing.map(String).join(", ")}
          </span>
        )}
      </div>
      <ScoreBar
        label="Trade readiness"
        value={
          typeof tc.trade_readiness_score_0_100 === "number"
            ? tc.trade_readiness_score_0_100
            : null
        }
        max={100}
      />
      <pre className="max-h-56 overflow-auto rounded-lg bg-black/30 p-3 font-mono text-xs text-slate-400">
        {JSON.stringify(tc, null, 2)}
      </pre>
    </div>
  );
}

function PipelineTraceSection({ trace }: { trace: unknown }) {
  if (!Array.isArray(trace) || trace.length === 0) {
    return <p className="text-sm text-slate-500">No pipeline trace.</p>;
  }
  return (
    <div className="overflow-x-auto text-xs">
      <table className="w-full border-collapse text-left text-slate-300">
        <thead>
          <tr className="border-b border-surface-border text-slate-500">
            <th className="py-2 pr-4 font-medium">Stage</th>
            <th className="py-2 pr-4 font-medium">Duration (ms)</th>
            <th className="py-2 font-medium">OK</th>
          </tr>
        </thead>
        <tbody>
          {trace.map((row, i) => {
            if (!isRecord(row)) return null;
            return (
              <tr key={i} className="border-b border-surface-border/60">
                <td className="py-1.5 pr-4 font-mono text-sky-200/90">{String(row.stage ?? "—")}</td>
                <td className="py-1.5 pr-4">{String(row.duration_ms ?? "—")}</td>
                <td className="py-1.5">{String(row.ok ?? "—")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RunSummaryBanner({
  payload,
  inner,
  pipelineStages,
}: {
  payload: Record<string, unknown>;
  inner: Record<string, unknown>;
  pipelineStages: string[];
}) {
  const startRaw = payload.analysis_period_start ?? inner.analysis_period_start;
  const endRaw = payload.analysis_period_end ?? inner.analysis_period_end;
  const items: { label: string; value: string }[] = [
    { label: "Symbol", value: String(payload.symbol ?? inner.symbol ?? "—") },
    {
      label: "Analysis window",
      value: `${formatYmdOnly(startRaw as string | undefined)} → ${formatYmdOnly(endRaw as string | undefined)}`,
    },
    { label: "Output dir", value: String(payload.output_dir ?? inner.output_dir ?? "—") },
    { label: "Pipeline", value: String(inner.pipeline_kind ?? inner.pipeline_version ?? "—") },
    {
      label: "Stages executed",
      value:
        pipelineStages.length > 0
          ? pipelineStages.join(", ")
          : "—",
    },
  ];
  return (
    <section className="rounded-xl border border-sky-900/30 bg-sky-950/20 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-sky-400/90">Run summary</h3>
      <MetricGrid items={items} />
    </section>
  );
}

/** Renders structured layers for `/api/tools/run/single` (equity research compact payload). */
export function PeadSingleResultView({ payload }: { payload: unknown }) {
  if (!isRecord(payload)) return null;

  const inner = payload.result;
  if (!isRecord(inner)) return null;

  if (inner.success === false) {
    const msg = inner.error ?? payload.error ?? "Run did not complete.";
    return (
      <div className="mt-8 space-y-2">
        <h2 className="text-sm font-semibold text-slate-300">Run result</h2>
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 text-sm text-amber-100">
          {String(msg)}
        </div>
        <p className="text-xs text-slate-500">
          Check the full JSON panel below for the raw API response.
        </p>
      </div>
    );
  }

  const ta = isRecord(inner.technical_analysis) ? inner.technical_analysis : undefined;
  const fa = isRecord(inner.fundamental_analysis) ? inner.fundamental_analysis : undefined;
  const ns = inner.news_sentiment;
  const tc = inner.trade_context;
  const ttr = isRecord(inner.technical_tool_response) ? inner.technical_tool_response : undefined;
  const toolError =
    typeof inner.technical_tool_error === "string"
      ? inner.technical_tool_error
      : ttr && ttr.success === false && typeof ttr.error === "string"
        ? ttr.error
        : undefined;
  const ntr = isRecord(inner.news_tool_response) ? inner.news_tool_response : undefined;
  const ms = inner.market_sentiment;
  const mtr = isRecord(inner.market_tool_response) ? inner.market_tool_response : undefined;

  const brief =
    typeof inner.research_brief_excerpt === "string" ? inner.research_brief_excerpt : "";
  const pipelineStages = Array.isArray(inner.equity_pipeline_stages)
    ? (inner.equity_pipeline_stages as unknown[]).filter((x) => typeof x === "string")
    : [];
  const chartPayload = technicalChartFromInner(inner);

  return (
    <div className="mt-8 space-y-4">
      <h2 className="text-sm font-semibold text-slate-300">Run result</h2>
      <p className="text-xs text-slate-500">
        OHLCV, technical, news, optional market-context headlines, and trade-context price logic use
        the analysis window above. Fundamentals are a company-level snapshot, not tied bar-by-bar to
        that range.
        Full JSON is in the panel below.
      </p>

      <RunSummaryBanner payload={payload} inner={inner} pipelineStages={pipelineStages as string[]} />

      {chartPayload ? (
        <section className="rounded-xl border border-surface-border bg-surface-raised/20 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Technical chart (same payload as Technical tool)
          </h3>
          <div className="mt-3">
            <TechnicalAnalysisChart
              chart={chartPayload}
              calendarWindow={
                typeof inner.price_fetch_calendar_start === "string" &&
                typeof inner.price_fetch_calendar_end === "string"
                  ? {
                      start: inner.price_fetch_calendar_start,
                      end: inner.price_fetch_calendar_end,
                    }
                  : undefined
              }
            />
          </div>
        </section>
      ) : null}

      {brief.length > 0 && (
        <section className="rounded-xl border border-surface-border bg-slate-900/40 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Research brief (excerpt)
          </h3>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-300">
            {brief}
          </pre>
        </section>
      )}

      <CollapsibleToolSection title="Technical analysis" defaultOpen>
        <TechnicalSection ta={ta} toolError={toolError} toolMeta={ttr} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Technical trade plan (AI)" defaultOpen>
        <TechnicalAiVerdictSection
          requested={inner.technical_include_ai_verdict as boolean | undefined}
          verdict={ttr && isRecord(ttr) ? ttr.research_verdict : undefined}
        />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Fundamental analysis (screening)" defaultOpen>
        <FundamentalSection fa={fa} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="News sentiment" defaultOpen>
        <NewsSection ns={ns} layer={ntr} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Market sentiment" defaultOpen>
        <MarketSentimentSection ms={ms} layer={mtr} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Trade / execution context" defaultOpen={false}>
        <TradeContextSection tc={tc} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Research desk (AI)" defaultOpen>
        <ResearchDeskSection desk={inner.research_desk} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Pipeline stages (timing)" defaultOpen={false}>
        <PipelineTraceSection trace={inner.pipeline_trace} />
      </CollapsibleToolSection>
    </div>
  );
}
