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
    ma_short?: (number | null)[];
    ma_long?: (number | null)[];
    rsi: (number | null)[];
    macd: (number | null)[];
    macd_signal: (number | null)[];
    macd_histogram: (number | null)[];
    volume: (number | null)[];
    bb_upper?: (number | null)[];
    bb_mid?: (number | null)[];
    bb_lower?: (number | null)[];
    stoch_k?: (number | null)[];
    stoch_d?: (number | null)[];
    /** Anchored VWAP from first bar of window */
    vwap?: (number | null)[];
    supertrend?: (number | null)[];
    keltner_upper?: (number | null)[];
    keltner_lower?: (number | null)[];
    adx?: (number | null)[];
    plus_di?: (number | null)[];
    minus_di?: (number | null)[];
  };
  periods: {
    ma_short?: number;
    ma_long?: number;
    rsi: number;
    bb?: number;
    stoch_k?: number;
    adx?: number;
    supertrend?: number;
    cmf?: number;
  };
  support_resistance: {
    support: { price: number; label: string }[];
    resistance: { price: number; label: string }[];
    method: string;
  };
  window?: { first_bar?: string | null; last_bar?: string | null; rows?: number };
};
