/**
 * rollingAverage.ts — Client-side 1Y/3Y/5Y/10Y/LT rolling averages
 *
 * Ported from cissa_merged/cissa/frontend/src/utils/rollingAverage.ts
 *
 * Usage:
 *   const rawRows = metricsData.map(r => ({ ticker: r.ticker, year: r.fiscal_year, value: r.value }));
 *   const rolling = computeRollingAverages(rawRows);
 *   // → [{ year: 2020, y1: 12.3, y3: 11.1, y5: null, y10: null, lt: 8.1 }, ...]
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RawRow {
  ticker: string;
  year:   number;
  value:  number | null;
}

/**
 * One year's output from `computeRollingAverages`.
 * All values are in the same unit as the input (e.g. %).
 * null = insufficient data for that window.
 */
export interface RollingRow {
  year: number;
  /** 1-year simple average across all tickers for that year */
  y1:  number | null;
  /** 3-year trailing simple average (years [y-2, y-1, y]) */
  y3:  number | null;
  /** 5-year trailing simple average */
  y5:  number | null;
  /** 10-year trailing simple average */
  y10: number | null;
  /** Long-term: cumulative mean of all 1Y cross-sectional averages up to this year */
  lt:  number | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function mean(values: (number | null)[]): number | null {
  const valid = values.filter((v): v is number => v !== null && isFinite(v));
  if (valid.length === 0) return null;
  return valid.reduce((s, v) => s + v, 0) / valid.length;
}

function rollingWindow(
  yearMeans: Array<{ year: number; avg: number | null }>,
  window: number,
): Map<number, number | null> {
  const result = new Map<number, number | null>();
  for (let i = 0; i < yearMeans.length; i++) {
    if (i + 1 < window) {
      result.set(yearMeans[i].year, null);
    } else {
      const slice = yearMeans.slice(i + 1 - window, i + 1).map(r => r.avg);
      result.set(yearMeans[i].year, mean(slice));
    }
  }
  return result;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

/**
 * Compute 1Y/3Y/5Y/10Y/LT rolling cross-sectional averages.
 * Input: flat per-ticker-per-year rows. Output: one row per year.
 */
export function computeRollingAverages(rows: RawRow[]): RollingRow[] {
  if (rows.length === 0) return [];

  // Cross-sectional mean per year
  const byYear = new Map<number, (number | null)[]>();
  for (const r of rows) {
    if (!byYear.has(r.year)) byYear.set(r.year, []);
    byYear.get(r.year)!.push(r.value);
  }

  const sortedYears = Array.from(byYear.keys()).sort((a, b) => a - b);
  const yearMeans = sortedYears.map(yr => ({ year: yr, avg: mean(byYear.get(yr)!) }));

  const r1  = rollingWindow(yearMeans, 1);
  const r3  = rollingWindow(yearMeans, 3);
  const r5  = rollingWindow(yearMeans, 5);
  const r10 = rollingWindow(yearMeans, 10);

  // LT = cumulative mean of 1Y cross-sectional averages
  const ltMap = new Map<number, number | null>();
  const cumulative: (number | null)[] = [];
  for (const { year, avg } of yearMeans) {
    cumulative.push(avg);
    ltMap.set(year, mean(cumulative));
  }

  return sortedYears.map(yr => ({
    year: yr,
    y1:  r1.get(yr)  ?? null,
    y3:  r3.get(yr)  ?? null,
    y5:  r5.get(yr)  ?? null,
    y10: r10.get(yr) ?? null,
    lt:  ltMap.get(yr) ?? null,
  }));
}

/**
 * Build RollingRow[] from pre-windowed get_metrics data.
 * Use when backend already stores 1Y/3Y/5Y/10Y series separately
 * (e.g. Calc 1Y TER-KE, Calc 3Y TER-KE …).
 * Computes LT client-side as cumulative mean of y1 values.
 */
export function buildRollingFromWindowed(
  y1Data:  { year: number; value: number }[],
  y3Data:  { year: number; value: number }[],
  y5Data:  { year: number; value: number }[],
  y10Data: { year: number; value: number }[],
  /** Multiply values before storing (e.g. ×100 to convert 0.12 → 12%) */
  scale = 1,
): RollingRow[] {
  if (y1Data.length === 0) return [];

  const toMap = (arr: { year: number; value: number }[]) =>
    new Map(arr.map(d => [d.year, d.value * scale]));

  const m1  = toMap(y1Data);
  const m3  = toMap(y3Data);
  const m5  = toMap(y5Data);
  const m10 = toMap(y10Data);

  const years = Array.from(new Set([
    ...y1Data.map(d => d.year),
    ...y3Data.map(d => d.year),
    ...y5Data.map(d => d.year),
    ...y10Data.map(d => d.year),
  ])).sort((a, b) => a - b);

  // LT = cumulative mean of y1 values
  const ltMap = new Map<number, number | null>();
  const cumY1: number[] = [];
  for (const yr of years) {
    const v = m1.get(yr);
    if (v !== undefined) cumY1.push(v);
    ltMap.set(yr, cumY1.length ? cumY1.reduce((s, x) => s + x, 0) / cumY1.length : null);
  }

  return years.map(yr => ({
    year: yr,
    y1:  m1.get(yr)  ?? null,
    y3:  m3.get(yr)  ?? null,
    y5:  m5.get(yr)  ?? null,
    y10: m10.get(yr) ?? null,
    lt:  ltMap.get(yr) ?? null,
  }));
}
