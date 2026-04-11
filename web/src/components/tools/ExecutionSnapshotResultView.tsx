import {
  CollapsibleToolSection,
  TechnicalSection,
  TradeContextSection,
} from "./PeadSingleResultView";

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** Structured technical + trade context for `/api/tools/run/execution-snapshot`. */
export function ExecutionSnapshotResultView({ payload }: { payload: unknown }) {
  if (!isRecord(payload)) return null;

  if (payload.success === false) {
    return (
      <div className="mt-8 space-y-2">
        <h2 className="text-sm font-semibold text-slate-300">Snapshot layers</h2>
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 text-sm text-amber-100">
          {String(payload.error ?? "Snapshot failed")}
        </div>
      </div>
    );
  }

  const ta = isRecord(payload.technical_analysis) ? payload.technical_analysis : undefined;
  const note = typeof payload.note === "string" ? payload.note : "";

  return (
    <div className="mt-8 space-y-4">
      <h2 className="text-sm font-semibold text-slate-300">Snapshot layers</h2>
      {note ? <p className="text-xs text-slate-400">{note}</p> : null}
      <p className="text-xs text-slate-500">
        This run does not include PEAD, fundamentals, or news. Open{" "}
        <strong className="font-medium text-slate-400">PEAD — single symbol</strong> for full desk
        layers.
      </p>
      <CollapsibleToolSection title="Technical analysis" defaultOpen>
        <TechnicalSection ta={ta} />
      </CollapsibleToolSection>
      <CollapsibleToolSection title="Trade / execution context" defaultOpen>
        <TradeContextSection tc={payload.trade_context} />
      </CollapsibleToolSection>
    </div>
  );
}
