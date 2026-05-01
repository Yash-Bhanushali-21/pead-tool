import {
  EQUITY_PIPELINE_STAGE_IDS,
  EQUITY_PIPELINE_STAGE_LABELS,
  type EquityPipelineStageId,
} from "../../lib/equityPipelineStages";

export type StageToggleMap = Record<EquityPipelineStageId, boolean>;

export function defaultStageTogglesAllOn(): StageToggleMap {
  return Object.fromEntries(EQUITY_PIPELINE_STAGE_IDS.map((id) => [id, true])) as StageToggleMap;
}

function setAll(value: boolean): StageToggleMap {
  return Object.fromEntries(EQUITY_PIPELINE_STAGE_IDS.map((id) => [id, value])) as StageToggleMap;
}

const PRESET_TECH_ONLY: Partial<StageToggleMap> = {
  fetch_price_window: true,
  run_technical_tool: true,
};

const PRESET_FUND_ONLY: Partial<StageToggleMap> = {
  fetch_price_window: false,
  resolve_output_dir: false,
  run_fundamentals_tool: true,
  run_exchange_announcements: false,
  run_technical_tool: false,
  run_news_tool: false,
  run_market_sentiment_tool: false,
  run_trade_context: false,
  run_research_desk: false,
};

const PRESET_NEWS_INTEL: Partial<StageToggleMap> = {
  fetch_price_window: false,
  resolve_output_dir: false,
  run_fundamentals_tool: false,
  run_exchange_announcements: true,
  run_technical_tool: false,
  run_news_tool: true,
  run_market_sentiment_tool: true,
  run_trade_context: false,
  run_research_desk: false,
};

function applyPreset(base: Partial<StageToggleMap>): StageToggleMap {
  const out = defaultStageTogglesAllOn();
  for (const id of EQUITY_PIPELINE_STAGE_IDS) {
    if (Object.prototype.hasOwnProperty.call(base, id)) {
      out[id] = Boolean(base[id]);
    }
  }
  return out;
}

export function EquityPipelineStagePicker({
  toggles,
  onChange,
}: {
  toggles: StageToggleMap;
  onChange: (next: StageToggleMap) => void;
}) {
  const toggle = (id: EquityPipelineStageId) => {
    onChange({ ...toggles, [id]: !toggles[id] });
  };

  return (
    <div className="space-y-3 rounded-xl border border-surface-border bg-surface-raised/15 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-200">Pipeline stages</p>
          <p className="text-xs text-slate-500">
            Uncheck steps to skip them (symbol news, market-context headlines, research desk LLM, etc.).
            OHLCV
            fetch is added on the server when a selected step needs prices. All on (default) runs the
            full pipeline.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-600 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-200 hover:border-slate-500"
            onClick={() => onChange(setAll(true))}
          >
            All on
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-600 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-200 hover:border-slate-500"
            onClick={() => onChange(setAll(false))}
          >
            All off
          </button>
          <button
            type="button"
            className="rounded-lg border border-sky-800/60 bg-sky-950/40 px-2.5 py-1 text-xs text-sky-100 hover:bg-sky-950/70"
            onClick={() => onChange(applyPreset(PRESET_TECH_ONLY))}
          >
            OHLCV + technical
          </button>
          <button
            type="button"
            className="rounded-lg border border-sky-800/60 bg-sky-950/40 px-2.5 py-1 text-xs text-sky-100 hover:bg-sky-950/70"
            onClick={() => onChange(applyPreset(PRESET_FUND_ONLY))}
          >
            Fundamentals only
          </button>
          <button
            type="button"
            className="rounded-lg border border-sky-800/60 bg-sky-950/40 px-2.5 py-1 text-xs text-sky-100 hover:bg-sky-950/70"
            onClick={() => onChange(applyPreset(PRESET_NEWS_INTEL))}
          >
            News intelligence
          </button>
        </div>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {EQUITY_PIPELINE_STAGE_IDS.map((id) => {
          const meta = EQUITY_PIPELINE_STAGE_LABELS[id];
          return (
            <li key={id}>
              <label className="flex cursor-pointer gap-2 rounded-lg border border-slate-800/80 bg-black/20 px-3 py-2 hover:border-slate-700">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={toggles[id]}
                  onChange={() => toggle(id)}
                />
                <span className="text-xs">
                  <span className="font-medium text-slate-200">{meta.title}</span>
                  <span className="mt-0.5 block font-mono text-[10px] text-slate-600">{id}</span>
                  <span className="mt-1 block text-slate-500">{meta.hint}</span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function buildPipelineStagesBody(toggles: StageToggleMap): { pipeline_stages?: string[] } {
  const allOn = EQUITY_PIPELINE_STAGE_IDS.every((id) => toggles[id]);
  if (allOn) return {};
  return {
    pipeline_stages: EQUITY_PIPELINE_STAGE_IDS.filter((id) => toggles[id]),
  };
}
