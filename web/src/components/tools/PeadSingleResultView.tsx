import { useState } from "react";

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
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

export function TechnicalSection({ ta }: { ta: Record<string, unknown> | undefined }) {
  if (!ta || Object.keys(ta).length === 0) {
    return <p className="text-sm text-slate-500">No technical snapshot in this response.</p>;
  }
  const scores = isRecord(ta.scores) ? ta.scores : {};
  const labels = isRecord(ta.labels) ? ta.labels : {};
  const last = isRecord(ta.last) ? ta.last : {};
  const notes = Array.isArray(ta.notes) ? ta.notes : [];

  return (
    <div className="space-y-3 text-sm text-slate-300">
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
      <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-3">
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
        Pillars are scored 0–25 each (valuation, quality, balance sheet, growth). Additional lines
        and charts are written under the run output directory when the job succeeds.
      </p>
    </div>
  );
}

function NewsSection({ ns }: { ns: unknown }) {
  if (ns === null || ns === undefined) {
    return (
      <p className="text-sm text-slate-500">
        News and sentiment were not included (turn off &quot;Include news&quot; or pipeline returned
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
  return (
    <div className="space-y-3 text-sm text-slate-300">
      <ScoreBar
        label="News score"
        value={typeof ns.news_score_0_100 === "number" ? ns.news_score_0_100 : null}
        max={100}
      />
      <MetricGrid
        items={[
          { label: "Articles", value: String(ns.article_count ?? "—") },
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
    </div>
  );
}

export function TradeContextSection({ tc }: { tc: unknown }) {
  if (!isRecord(tc) || Object.keys(tc).length === 0) {
    return (
      <p className="text-sm text-slate-500">No trade / execution context block in this response.</p>
    );
  }
  return (
    <div className="space-y-2 text-sm text-slate-300">
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

/** Renders structured PEAD layers when present on `/api/tools/run/single` payload. */
export function PeadSingleResultView({ payload }: { payload: unknown }) {
  if (!isRecord(payload)) return null;

  const inner = payload.result;
  if (!isRecord(inner)) return null;

  if (inner.success === false) {
    const msg = inner.error ?? payload.error ?? "Run did not complete.";
    return (
      <div className="mt-8 space-y-2">
        <h2 className="text-sm font-semibold text-slate-300">Analysis layers</h2>
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 text-sm text-amber-100">
          {String(msg)}
        </div>
        <p className="text-xs text-slate-500">
          Partial or empty layers are expected when the pipeline fails — check raw JSON for details.
        </p>
      </div>
    );
  }

  const ta = isRecord(inner.technical_analysis) ? inner.technical_analysis : undefined;
  const fa = isRecord(inner.fundamental_analysis) ? inner.fundamental_analysis : undefined;
  const ns = inner.news_sentiment;
  const tc = inner.trade_context;

  const brief =
    typeof inner.research_brief_excerpt === "string" ? inner.research_brief_excerpt : "";

  return (
    <div className="mt-8 space-y-4">
      <h2 className="text-sm font-semibold text-slate-300">Analysis layers</h2>
      <p className="text-xs text-slate-500">
        Same fields as the API compact payload: technicals, screening fundamentals, optional news,
        and trade context. Use raw JSON below for full detail (CARs, market model, etc.).
      </p>

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
        <TechnicalSection ta={ta} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Fundamental analysis (screening)" defaultOpen>
        <FundamentalSection fa={fa} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="News sentiment" defaultOpen>
        <NewsSection ns={ns} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Trade / execution context" defaultOpen={false}>
        <TradeContextSection tc={tc} />
      </CollapsibleToolSection>
    </div>
  );
}
