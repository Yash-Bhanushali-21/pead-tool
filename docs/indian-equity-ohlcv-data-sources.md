# Indian equity OHLCV: closing the gap between requested window and returned bars

**Purpose:** Research inputs for choosing feeds when the **requested** calendar window (e.g. 2020-01-01 → 2026-04-19) **diverges** from **vendor bars** (e.g. 2025-10-30 → 2026-04-17).  
**Not:** Legal, compliance, or execution advice; not an endorsement of any vendor.

---

## 1. Context — what the discrepancy actually implies

You observe:

- **Requested OHLCV window:** wide calendar span (multi-year).
- **Vendor bars in response:** shorter strip (here ~113 daily sessions).

**Fact:** The application is passing your window into the fetch path; the limitation is **upstream coverage** (or **symbol identity**), not the chart clipper alone.

**Inference (conditional):** A multi-year gap usually means one or more of:

1. **Listing / series** — The security did not trade on that ticker/exchange before the first returned bar (IPO, SME migration, scheme of arrangement, new ISIN).
2. **Vendor depth** — The free or convenience feed does not carry full history for that line item even if the company is older (common on thin SME / renamed symbols).
3. **Wrong line** — `SYMBOL.NS` vs `SYMBOL.BO`, or wrong series (EQ vs BE etc.) maps to a different instrument with shorter history.
4. **Session calendar** — Missing holidays vs bad dates is secondary; a **years**-long gap is almost never “calendar bug.”

**What would change the view:** Exchange or issuer records showing **continuous** listing under the same ISIN since before 2025-10-30 would push you toward **feed quality**; if listing is genuinely recent, **no vendor** will produce 2020 bars for that ticker.

---

## 2. Evidence checklist before spending on data

Do this **per symbol** (cheap, high signal):

| Check | Why |
|--------|-----|
| **NSE/BSE circulars + listing date** | Confirms whether 2020 prices *should* exist for *this* ticker. |
| **ISIN** | Stable identifier across renames; map to correct EQ series. |
| **Parallel query `.BO` vs `.NS` on Yahoo** | Quick heuristic for dual-listed or BSE-led history (still not ground truth). |
| **First/last trade date from a second vendor** | If two independent paid feeds agree on the same first bar, treat “missing 2020” as **instrument reality** not **bug**. |

---

## 3. Selection criteria (how a desk would score vendors)

| Criterion | Question |
|-----------|----------|
| **Coverage** | NSE EQ, BSE, SME, indices; depth in *years* for daily; intraday retention by interval. |
| **Corporate actions** | Split/bonus/dividend adjustment flags; corporate-action calendar. |
| **Latency & mode** | EOD batch vs delayed vs real-time; session rules (India cash market). |
| **License** | Redistribution into your product vs research-only vs display-only; audit trail. |
| **Symbology** | ISIN ↔ ticker ↔ exchange; handling of name changes. |
| **Ops** | SLA, gap fills, holiday alignment, support for bad prints. |

**Risk-first default:** For any production or client-facing analytics, assume **exchange-licensed or clearly sublicensed** data unless counsel confirms otherwise.

---

## 4. Tiered landscape (sources that *can* return longer or official series)

Tiers are **rough**; vendors move SKUs often—validate in trial against a few known liquid names *and* your problem SME names.

### Tier A — Exchange-sourced or exchange-licensed (strongest chain of custody)

- **NSE / BSE data products (paid)** — Historical and intraday products aimed at institutions and data redistributors. **Highest** alignment with official tape for **that** exchange. **Cost and contracts** are the friction.

### Tier B — India-focused commercial datafeeds (API / file delivery)

Examples (non-exhaustive; **verify** current SKUs and licensing):

- **Global Datafeeds** (India) — Markets API stack covering NSE/BSE and derivatives; vendor documentation describes long-dated **daily** history and multiple **minute** granularities with stated backfill limits (confirm per product). Useful when you need **systematic** India coverage beyond Yahoo.
- **TrueData** (India) — Widely referenced in Indian retail/pro context for historical + streaming; **terms** and **history depth** must be confirmed for your use case (especially redistribution).
- **EODData** — Long-running EOD / historical vendor with NSE/BSE coverage; check **symbol universe** and **API** vs file-based access for automation.

**Desk note:** These vendors exist precisely because **free** Yahoo/NSE scraping paths are **incomplete and brittle** for SME and for compliance-sensitive use.

### Tier C — Global aggregators (good for multi-region books; India depth varies)

Used on many institutional stacks; **India SME** may still be thinner than Tier B for the same symbol—**trial** is mandatory.

- **Refinitiv / LSEG**, **Bloomberg**, **FactSet**, **S&P Capital IQ**, **ICE** — Terminal or enterprise contracts; symbology and corporate actions are strengths; cost reflects that.
- **Polygon.io**, **Tiingo**, **EOD Historical Data** — API-first; **India coverage and history depth** are product-version dependent—do not assume parity with US equities.

### Tier D — Broker / OMS APIs (strong for *authorized* accounts, weak for *redistribution*)

- **Zerodha Kite Connect**, **Upstox**, and peers — Often excellent for **your** account’s instruments and recent history; **license** usually **blocks** storing and republishing full history to arbitrary end users. Appropriate for **personal** or **internal** research tied to that broker, not as a generic app backend without legal review.

### Tier E — Free / open convenience (current repo baseline + adjacent)

- **Yahoo (`yfinance`)** — **Convenience**; depth and quality vary by symbol; not a primary tape. Upstream: [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) (not affiliated with Yahoo; see Yahoo terms of use there).
- **`jugaad-data` (NSE site)** — In this repo, wired as a **third** daily OHLCV attempt **after** NSE (`nse` package) and Yahoo, when both return no rows. Targets the **current** NSE website; includes client-side caching — still subject to NSE availability and **license/ToS** (see [jugaad-py/jugaad-data](https://github.com/jugaad-py/jugaad-data) and project docs). **Does not guarantee** deeper history than Yahoo for every SME; validate per symbol.
- **NSE unofficial / community packages** — Can break when NSE changes pages/APIs; column mapping issues already force fallbacks in practice.
- **Open-source NSE scrapers** — Same **fragility** and **ToS** risks; ok for ad-hoc research, risky as sole production source.

---

## 5. Intraday (5m / 15m / 1h) — separate product decision

**Fact:** Intraday history length is **interval-dependent** and almost always **shorter** than daily at free tiers (Yahoo enforces strict lookback windows by interval).

**Inference:** If the product roadmap includes **years** of 5m bars for Indian names, budget for **Tier A or B** with explicit minute retention in the contract, not “just more Yahoo.”

---

## 6. Implementation direction for *this* codebase (when you pick a vendor)

- **Pluggable `OHLCVProvider`** — Config + env selects primary feed; keep Yahoo/NSE as fallback or cross-check.
- **Merge policy** — If combining feeds: define **precedence**, **dedupe** on session date, **log** row-level source for audit.
- **User-visible provenance** — You already surface requested vs vendor window; extend with **data_source** and **first_bar_source_id** when available.

---

## 7. Bottom line (analyst framing)

- The **113-session** strip vs a **2020–2026** request is **consistent with** either (a) **late listing / short vendor history** for that line, or (b) **insufficient feed tier** for that symbol—not necessarily a bug in your date picker.
- **Action:** Run section **2**; if listing is old, **pilot Tier B (or A)** on that symbol and compare first bar and session count. If listing is new, **accept** that pre-listing bars do not exist and narrow the research window in the UI copy.

---

## Disclaimer

Vendor names are **illustrative research pointers** only. Capabilities, pricing, and **terms of use** change; **no warranty** of fitness for a purpose. This document is **not** affiliated with any exchange or data vendor.
