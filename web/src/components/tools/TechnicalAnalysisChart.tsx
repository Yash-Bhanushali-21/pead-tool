import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import {
  CHART_CALENDAR_RANGE_DAYS,
  sliceChartByCalendarRange,
  type ChartCalendarRangeId,
} from "../../lib/chartPayloadSlice";
import type { TechnicalChartPayload } from "./technicalChartTypes";

export type { TechnicalChartPayload } from "./technicalChartTypes";

function lineData(
  times: string[],
  values: (number | null | undefined)[],
): { time: Time; value: number }[] {
  const out: { time: Time; value: number }[] = [];
  for (let i = 0; i < times.length; i++) {
    const v = values[i];
    if (v != null && Number.isFinite(v)) {
      out.push({ time: times[i] as Time, value: v });
    }
  }
  return out;
}

function histData(
  times: string[],
  values: (number | null)[],
): { time: Time; value: number; color?: string }[] {
  const out: { time: Time; value: number; color?: string }[] = [];
  for (let i = 0; i < times.length; i++) {
    const v = values[i];
    if (v != null && Number.isFinite(v)) {
      const up = v >= 0;
      out.push({
        time: times[i] as Time,
        value: v,
        color: up ? "rgba(56, 189, 248, 0.7)" : "rgba(248, 113, 113, 0.7)",
      });
    }
  }
  return out;
}

function volumeHistData(
  bars: TechnicalChartPayload["bars"],
): { time: Time; value: number; color: string }[] {
  return bars.map((b) => ({
    time: b.time as Time,
    value: b.volume,
    color:
      b.close >= b.open ? "rgba(34, 197, 94, 0.35)" : "rgba(239, 68, 68, 0.35)",
  }));
}

const commonLayout = {
  layout: {
    background: { type: ColorType.Solid, color: "#0b1220" },
    textColor: "#94a3b8",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: "#1e293b" },
    horzLines: { color: "#1e293b" },
  },
  crosshair: { mode: CrosshairMode.Normal },
};

function syncCharts(leader: IChartApi, followers: IChartApi[]) {
  leader.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (!range) return;
    for (const c of followers) {
      c.timeScale().setVisibleRange(range);
    }
  });
}

const RANGE_OPTIONS: { id: ChartCalendarRangeId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "1y", label: "1Y" },
  { id: "6m", label: "6M" },
  { id: "3m", label: "3M" },
  { id: "1m", label: "1M" },
  { id: "1w", label: "1W" },
  { id: "1d", label: "1D" },
];

export type TechnicalAnalysisChartProps = {
  chart: TechnicalChartPayload;
  /** Requested analysis window (optional) — shown vs actual bar coverage. */
  calendarWindow?: { start?: string; end?: string };
};

function Toggle({
  id,
  checked,
  onChange,
  label,
}: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label
      htmlFor={id}
      className="inline-flex cursor-pointer select-none items-center gap-1.5 rounded border border-slate-700/80 bg-slate-900/50 px-2 py-1 text-xs text-slate-300 hover:border-slate-600"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500/40"
      />
      {label}
    </label>
  );
}

export function TechnicalAnalysisChart({ chart, calendarWindow }: TechnicalAnalysisChartProps) {
  const priceRef = useRef<HTMLDivElement>(null);
  const volRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const stochRef = useRef<HTMLDivElement>(null);
  const adxRef = useRef<HTMLDivElement>(null);

  const [rangeId, setRangeId] = useState<ChartCalendarRangeId>("all");
  const [showBB, setShowBB] = useState(true);
  const [showSR, setShowSR] = useState(true);
  const [showVwap, setShowVwap] = useState(true);
  const [showSupertrend, setShowSupertrend] = useState(true);
  const [showKeltner, setShowKeltner] = useState(true);
  const [showVolume, setShowVolume] = useState(true);
  const [showRsi, setShowRsi] = useState(true);
  const [showMacd, setShowMacd] = useState(true);
  const [showStoch, setShowStoch] = useState(true);
  const [showAdx, setShowAdx] = useState(true);

  const displayChart = useMemo(
    () => sliceChartByCalendarRange(chart, rangeId),
    [chart, rangeId],
  );

  useEffect(() => {
    const pEl = priceRef.current;
    if (!pEl || !displayChart.bars?.length) return;

    const times = displayChart.bars.map((b) => b.time);
    const candleData = displayChart.bars.map((b) => ({
      time: b.time as Time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));

    const w = pEl.clientWidth || 800;

    const priceChart = createChart(pEl, {
      ...commonLayout,
      width: w,
      height: 300,
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: false, secondsVisible: false },
    });

    const candle = priceChart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candle.setData(candleData);

    const ind = displayChart.indicators;
    const bbP = displayChart.periods.bb ?? 20;
    if (showBB) {
      if (ind.bb_upper?.length) {
        const u = priceChart.addLineSeries({
          color: "rgba(251, 191, 36, 0.75)",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          title: `BB upper ${bbP}`,
        });
        u.setData(lineData(times, ind.bb_upper));
      }
      if (ind.bb_mid?.length) {
        const mid = priceChart.addLineSeries({
          color: "rgba(148, 163, 184, 0.85)",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          title: `BB mid ${bbP}`,
        });
        mid.setData(lineData(times, ind.bb_mid));
      }
      if (ind.bb_lower?.length) {
        const lo = priceChart.addLineSeries({
          color: "rgba(56, 189, 248, 0.75)",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          title: `BB lower ${bbP}`,
        });
        lo.setData(lineData(times, ind.bb_lower));
      }
    }

    if (showSR) {
      for (const r of displayChart.support_resistance.resistance ?? []) {
        candle.createPriceLine({
          price: r.price,
          color: "rgba(251, 191, 36, 0.9)",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: r.label,
        });
      }
      for (const s of displayChart.support_resistance.support ?? []) {
        candle.createPriceLine({
          price: s.price,
          color: "rgba(74, 222, 128, 0.9)",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: s.label,
        });
      }
    }

    const stP = displayChart.periods.supertrend ?? 10;
    if (showVwap && ind.vwap?.length) {
      const vw = priceChart.addLineSeries({
        color: "rgba(168, 85, 247, 0.95)",
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        title: "Anchored VWAP",
      });
      vw.setData(lineData(times, ind.vwap));
    }
    if (showSupertrend && ind.supertrend?.length) {
      const st = priceChart.addLineSeries({
        color: "rgba(34, 211, 238, 0.9)",
        lineWidth: 2,
        title: `Supertrend ${stP}`,
      });
      st.setData(lineData(times, ind.supertrend));
    }
    if (showKeltner && ind.keltner_upper?.length && ind.keltner_lower?.length) {
      const ku = priceChart.addLineSeries({
        color: "rgba(251, 113, 133, 0.7)",
        lineWidth: 1,
        title: "Keltner upper",
      });
      ku.setData(lineData(times, ind.keltner_upper));
      const kl = priceChart.addLineSeries({
        color: "rgba(52, 211, 153, 0.7)",
        lineWidth: 1,
        title: "Keltner lower",
      });
      kl.setData(lineData(times, ind.keltner_lower));
    }

    const followers: IChartApi[] = [];
    let volChart: IChartApi | null = null;
    let rsiChart: IChartApi | null = null;
    let macdChart: IChartApi | null = null;
    let stochChart: IChartApi | null = null;
    let adxChart: IChartApi | null = null;

    const vEl = volRef.current;
    if (showVolume && vEl) {
      volChart = createChart(vEl, {
        ...commonLayout,
        width: w,
        height: 72,
        rightPriceScale: { borderColor: "#334155" },
        timeScale: { visible: false },
      });
      const volHist = volChart.addHistogramSeries({ color: "#38bdf8" });
      volHist.setData(volumeHistData(displayChart.bars));
      followers.push(volChart);
    }

    const rEl = rsiRef.current;
    if (showRsi && rEl) {
      rsiChart = createChart(rEl, {
        ...commonLayout,
        width: w,
        height: 120,
        rightPriceScale: { borderColor: "#334155" },
        timeScale: { visible: false },
      });
      const rsiLine = rsiChart.addLineSeries({
        color: "#f472b6",
        lineWidth: 2,
        title: `RSI ${displayChart.periods.rsi}`,
      });
      rsiLine.setData(lineData(times, ind.rsi));
      rsiLine.createPriceLine({
        price: 70,
        color: "rgba(248, 113, 113, 0.45)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
      });
      rsiLine.createPriceLine({
        price: 30,
        color: "rgba(74, 222, 128, 0.45)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
      });
      followers.push(rsiChart);
    }

    const mEl = macdRef.current;
    if (showMacd && mEl) {
      macdChart = createChart(mEl, {
        ...commonLayout,
        width: w,
        height: 130,
        rightPriceScale: { borderColor: "#334155" },
        timeScale: { visible: false },
      });
      const macdHist = macdChart.addHistogramSeries({ base: 0 });
      macdHist.setData(histData(times, ind.macd_histogram));
      const macdL = macdChart.addLineSeries({ color: "#38bdf8", lineWidth: 2, title: "MACD" });
      macdL.setData(lineData(times, ind.macd));
      const sigL = macdChart.addLineSeries({ color: "#fbbf24", lineWidth: 1, title: "Signal" });
      sigL.setData(lineData(times, ind.macd_signal));
      followers.push(macdChart);
    }

    const sEl = stochRef.current;
    if (showStoch && sEl) {
      stochChart = createChart(sEl, {
        ...commonLayout,
        width: w,
        height: 110,
        rightPriceScale: { borderColor: "#334155" },
        timeScale: { borderColor: "#334155", timeVisible: false, secondsVisible: false },
      });
      const sk = displayChart.periods.stoch_k ?? 14;
      const kLine = stochChart.addLineSeries({
        color: "#a78bfa",
        lineWidth: 2,
        title: `Stoch %K ${sk}`,
      });
      kLine.setData(lineData(times, ind.stoch_k ?? []));
      const dLine = stochChart.addLineSeries({
        color: "#fcd34d",
        lineWidth: 1,
        title: "%D",
      });
      dLine.setData(lineData(times, ind.stoch_d ?? []));
      kLine.createPriceLine({
        price: 80,
        color: "rgba(248, 113, 113, 0.35)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
      });
      kLine.createPriceLine({
        price: 20,
        color: "rgba(74, 222, 128, 0.35)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
      });
      followers.push(stochChart);
    }

    const aEl = adxRef.current;
    if (showAdx && aEl && ind.adx?.length) {
      adxChart = createChart(aEl, {
        ...commonLayout,
        width: w,
        height: 100,
        rightPriceScale: { borderColor: "#334155" },
        timeScale: { visible: false },
      });
      const adxP = displayChart.periods.adx ?? 14;
      const adxL = adxChart.addLineSeries({
        color: "#e879f9",
        lineWidth: 2,
        title: `ADX ${adxP}`,
      });
      adxL.setData(lineData(times, ind.adx));
      const pdiL = adxChart.addLineSeries({
        color: "#4ade80",
        lineWidth: 1,
        title: "+DI",
      });
      pdiL.setData(lineData(times, ind.plus_di ?? []));
      const mdiL = adxChart.addLineSeries({
        color: "#f87171",
        lineWidth: 1,
        title: "-DI",
      });
      mdiL.setData(lineData(times, ind.minus_di ?? []));
      adxL.createPriceLine({
        price: 25,
        color: "rgba(148, 163, 184, 0.45)",
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
      });
      followers.push(adxChart);
    }

    if (followers.length) syncCharts(priceChart, followers);

    const charts: IChartApi[] = [priceChart, ...followers];
    const ro = new ResizeObserver(() => {
      const nw = pEl.clientWidth;
      if (nw < 200) return;
      for (const c of charts) c.applyOptions({ width: nw });
    });
    ro.observe(pEl);

    return () => {
      ro.disconnect();
      for (const c of charts) c.remove();
    };
  }, [
    displayChart,
    showBB,
    showSR,
    showVwap,
    showSupertrend,
    showKeltner,
    showVolume,
    showRsi,
    showMacd,
    showStoch,
    showAdx,
  ]);

  if (!chart.bars?.length) return null;

  const win = displayChart.window;
  const fullWin = chart.window;
  const reqStart = calendarWindow?.start?.trim();
  const reqEnd = calendarWindow?.end?.trim();
  const rangeDaysLabel =
    rangeId === "all" ? null : `${CHART_CALENDAR_RANGE_DAYS[rangeId]}d lookback from last bar`;

  return (
    <div className="mt-6 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-300">
          Price — Bollinger, VWAP, Supertrend, Keltner, pivot S/R
        </h3>
        <p className="max-w-xl text-xs text-slate-500">{displayChart.support_resistance.method}</p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-surface-border pb-3">
        <span className="w-full text-[10px] font-medium uppercase tracking-wide text-slate-500">
          Daily window (from last bar)
        </span>
        {RANGE_OPTIONS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setRangeId(id)}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              rangeId === id
                ? "bg-sky-600 text-white"
                : "border border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="w-full pt-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
          Intraday (not loaded — daily OHLCV only)
        </span>
        {(["5m", "15m", "1h"] as const).map((label) => (
          <button
            key={label}
            type="button"
            disabled
            title="Intraday bars are not fetched in this app yet; see docs/indian-equity-ohlcv-data-sources.md"
            className="cursor-not-allowed rounded border border-slate-800 bg-slate-950/50 px-2.5 py-1 text-xs text-slate-600"
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Toggle id="ch-bb" checked={showBB} onChange={setShowBB} label="Bollinger" />
        <Toggle id="ch-sr" checked={showSR} onChange={setShowSR} label="S/R lines" />
        <Toggle id="ch-vwap" checked={showVwap} onChange={setShowVwap} label="VWAP" />
        <Toggle id="ch-st" checked={showSupertrend} onChange={setShowSupertrend} label="Supertrend" />
        <Toggle id="ch-kc" checked={showKeltner} onChange={setShowKeltner} label="Keltner" />
        <Toggle id="ch-vol" checked={showVolume} onChange={setShowVolume} label="Volume pane" />
        <Toggle id="ch-rsi" checked={showRsi} onChange={setShowRsi} label="RSI" />
        <Toggle id="ch-macd" checked={showMacd} onChange={setShowMacd} label="MACD" />
        <Toggle id="ch-stoch" checked={showStoch} onChange={setShowStoch} label="Stochastic" />
        <Toggle id="ch-adx" checked={showAdx} onChange={setShowAdx} label="ADX / DI" />
      </div>

      {reqStart && reqEnd ? (
        <p className="text-xs text-slate-500">
          Requested OHLCV window:{" "}
          <span className="font-mono text-slate-400">
            {reqStart} → {reqEnd}
          </span>
          {fullWin?.first_bar && fullWin?.last_bar ? (
            <>
              {" "}
              · Vendor bars in response:{" "}
              <span className="font-mono text-slate-400">
                {fullWin.first_bar} → {fullWin.last_bar}
              </span>
              {fullWin.rows != null ? (
                <span className="text-slate-600"> ({fullWin.rows} sessions)</span>
              ) : null}
            </>
          ) : null}
        </p>
      ) : null}
      {win?.first_bar && win?.last_bar ? (
        <p className="text-xs text-slate-500">
          {reqStart && reqEnd ? "Visible on chart (range filter): " : "Chart bars: "}
          <span className="font-mono text-slate-400">{win.first_bar}</span> →{" "}
          <span className="font-mono text-slate-400">{win.last_bar}</span>
          {win.rows != null ? <span className="text-slate-600"> ({win.rows} sessions)</span> : null}
          {rangeDaysLabel ? (
            <span className="text-slate-600"> · {rangeDaysLabel}</span>
          ) : null}
        </p>
      ) : null}

      <div ref={priceRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
      {showVolume ? (
        <>
          <h3 className="pt-2 text-sm font-semibold text-slate-300">Volume</h3>
          <div ref={volRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
        </>
      ) : (
        <div ref={volRef} className="hidden" />
      )}
      {showRsi ? (
        <>
          <h3 className="pt-2 text-sm font-semibold text-slate-300">RSI</h3>
          <div ref={rsiRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
        </>
      ) : (
        <div ref={rsiRef} className="hidden" />
      )}
      {showMacd ? (
        <>
          <h3 className="pt-2 text-sm font-semibold text-slate-300">MACD</h3>
          <div ref={macdRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
        </>
      ) : (
        <div ref={macdRef} className="hidden" />
      )}
      {showStoch ? (
        <>
          <h3 className="pt-2 text-sm font-semibold text-slate-300">Stochastic</h3>
          <div ref={stochRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
        </>
      ) : (
        <div ref={stochRef} className="hidden" />
      )}
      {showAdx ? (
        <>
          <h3 className="pt-2 text-sm font-semibold text-slate-300">ADX / +DI / −DI</h3>
          <div ref={adxRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
        </>
      ) : (
        <div ref={adxRef} className="hidden" />
      )}
    </div>
  );
}
