/** Renders optional `research_verdict` from POST /api/tools/run/technical */

type VerdictPayload =
  | { text: string; model?: string }
  | { skipped: true; reason: string }
  | { error: string };

function splitMarkdownSections(text: string): { title: string; body: string }[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const parts = trimmed.split(/\n(?=## )/);
  return parts.map((block) => {
    const lines = block.trim().split("\n");
    const first = lines[0] ?? "";
    if (first.startsWith("## ")) {
      return {
        title: first.replace(/^##\s+/, "").trim(),
        body: lines.slice(1).join("\n").trim(),
      };
    }
    return { title: "", body: block.trim() };
  });
}

export function TechnicalVerdictPanel({ verdict }: { verdict: VerdictPayload }) {
  if ("skipped" in verdict && verdict.skipped) {
    return (
      <div className="rounded-2xl border border-amber-900/50 bg-amber-950/20 p-5 text-sm text-amber-100/90">
        <p className="font-semibold text-amber-200">AI research commentary</p>
        <p className="mt-2 text-amber-100/80">{verdict.reason}</p>
      </div>
    );
  }
  if ("error" in verdict) {
    return (
      <div className="rounded-2xl border border-rose-900/50 bg-rose-950/20 p-5 text-sm text-rose-100/90">
        <p className="font-semibold text-rose-200">AI research commentary failed</p>
        <p className="mt-2 font-mono text-xs opacity-90">{verdict.error}</p>
      </div>
    );
  }
  if (!("text" in verdict)) {
    return null;
  }
  const sections = splitMarkdownSections(verdict.text);
  return (
    <div className="rounded-2xl border border-slate-700/80 bg-slate-900/40 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-700/60 pb-3">
        <h2 className="text-sm font-semibold tracking-wide text-slate-200">
          Desk-style research note
        </h2>
        {verdict.model ? (
          <span className="font-mono text-xs text-slate-500">{verdict.model}</span>
        ) : null}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-amber-200/90">
        Educational commentary only — not investment advice. No representation of any broker or
        asset manager. Outcomes depend on fundamentals, liquidity, and events beyond this chart.
      </p>
      <div className="mt-5 space-y-5 text-sm text-slate-300">
        {sections.map((sec, i) =>
          sec.title ? (
            <section key={i}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                {sec.title}
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed text-slate-300">{sec.body}</div>
            </section>
          ) : (
            <div key={i} className="whitespace-pre-wrap leading-relaxed">
              {sec.body}
            </div>
          ),
        )}
      </div>
    </div>
  );
}

export function isResearchVerdict(v: unknown): v is VerdictPayload {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  if ("skipped" in o && o.skipped === true && typeof o.reason === "string") return true;
  if ("error" in o && typeof o.error === "string") return true;
  if ("text" in o && typeof o.text === "string") return true;
  return false;
}
