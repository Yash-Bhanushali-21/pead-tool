import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type Time,
} from "lightweight-charts";

export type TechnicalChartPayload = {
  bars: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
  indicators: {
    ma_short: (number | null)[];
    ma_long: (number | null)[];
    rsi: (number | null)[];
    macd: (number | null)[];
    macd_signal: (number | null)[];
    macd_histogram: (number | null)[];
    volume: (number | null)[];
  };
  periods: { ma_short: number; ma_long: number; rsi: number };
  support_resistance: {
    support: { price: number; label: string }[];
    resistance: { price: number; label: string }[];
    method: string;
  };
};

function lineData(
  times: string[],
  values: (number | null)[],
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

export function TechnicalAnalysisChart({ chart }: { chart: TechnicalChartPayload }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pEl = priceRef.current;
    const rEl = rsiRef.current;
    const mEl = macdRef.current;
    if (!pEl || !rEl || !mEl || !chart.bars?.length) return;

    const times = chart.bars.map((b) => b.time);
    const candleData = chart.bars.map((b) => ({
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
      height: 340,
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: true, secondsVisible: false },
    });

    const candle = priceChart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candle.setData(candleData);

    const ind = chart.indicators;
    const maS = priceChart.addLineSeries({
      color: "#38bdf8",
      lineWidth: 2,
      title: `MA ${chart.periods.ma_short}`,
    });
    maS.setData(lineData(times, ind.ma_short));

    const maL = priceChart.addLineSeries({
      color: "#c084fc",
      lineWidth: 2,
      title: `MA ${chart.periods.ma_long}`,
    });
    maL.setData(lineData(times, ind.ma_long));

    for (const r of chart.support_resistance.resistance ?? []) {
      candle.createPriceLine({
        price: r.price,
        color: "rgba(251, 191, 36, 0.85)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: r.label,
      });
    }
    for (const s of chart.support_resistance.support ?? []) {
      candle.createPriceLine({
        price: s.price,
        color: "rgba(74, 222, 128, 0.85)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: s.label,
      });
    }

    const rsiChart = createChart(rEl, {
      ...commonLayout,
      width: w,
      height: 140,
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { visible: false },
    });
    const rsiLine = rsiChart.addLineSeries({ color: "#f472b6", lineWidth: 2, title: `RSI ${chart.periods.rsi}` });
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

    const macdChart = createChart(mEl, {
      ...commonLayout,
      width: w,
      height: 160,
      rightPriceScale: { borderColor: "#334155" },
      timeScale: { borderColor: "#334155", timeVisible: true, secondsVisible: false },
    });
    const macdHist = macdChart.addHistogramSeries({ base: 0 });
    macdHist.setData(histData(times, ind.macd_histogram));
    const macdL = macdChart.addLineSeries({ color: "#38bdf8", lineWidth: 2, title: "MACD" });
    macdL.setData(lineData(times, ind.macd));
    const sigL = macdChart.addLineSeries({ color: "#fbbf24", lineWidth: 1, title: "Signal" });
    sigL.setData(lineData(times, ind.macd_signal));

    priceChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (!range) return;
      rsiChart.timeScale().setVisibleRange(range);
      macdChart.timeScale().setVisibleRange(range);
    });

    const ro = new ResizeObserver(() => {
      const nw = pEl.clientWidth;
      if (nw < 200) return;
      priceChart.applyOptions({ width: nw });
      rsiChart.applyOptions({ width: nw });
      macdChart.applyOptions({ width: nw });
    });
    ro.observe(pEl);

    return () => {
      ro.disconnect();
      priceChart.remove();
      rsiChart.remove();
      macdChart.remove();
    };
  }, [chart]);

  if (!chart.bars?.length) return null;

  return (
    <div className="mt-6 space-y-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-300">Price, MAs &amp; pivot S/R</h3>
        <p className="max-w-xl text-xs text-slate-500">{chart.support_resistance.method}</p>
      </div>
      <div ref={priceRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
      <h3 className="pt-2 text-sm font-semibold text-slate-300">RSI</h3>
      <div ref={rsiRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
      <h3 className="pt-2 text-sm font-semibold text-slate-300">MACD</h3>
      <div ref={macdRef} className="w-full overflow-hidden rounded-lg border border-surface-border" />
    </div>
  );
}
