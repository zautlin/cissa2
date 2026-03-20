/**
 * companyData.ts — Data layer between the companies/metrics API and the UI.
 *
 * RULE: UI components never consume raw ApiCompany or MetricResultItem directly.
 *       They only receive the typed local structures defined here.
 *
 * Transform chain:
 *   ApiCompany[]       → CompanyInfo[]        (mapApiCompanies)
 *   MetricResultItem[] → TickerLatestMap       (buildLatestByTicker)
 *   CompanyInfo[]
 *   + TickerLatestMaps → CompanyMetricRow[]    (buildCompanyMetricRows)
 *   CompanyMetricRow[] → SectorSummaryRow[]    (buildSectorSummary)
 */

import { ApiCompany, MetricResultItem } from "./api";

// ─── Local types ──────────────────────────────────────────────────────────────

export interface CompanyInfo {
  ticker:   string;
  name:     string;
  sector:   string;
  exchange: string;
}

export type EpCohort = "EP Dominant" | "Middle Group" | "EPS Dominant";

export interface CompanyMetricRow {
  ticker:   string;
  name:     string;
  sector:   string;
  /** TER-Ke as decimal (e.g. 0.082 = 8.2%) */
  terKe:    number | null;
  /** TER Alpha as decimal */
  terAlpha: number | null;
  /** EP Margin as decimal */
  epPct:    number | null;
  /** Full-year TSR as decimal */
  tsr:      number | null;
  cohort:   EpCohort;
}

export interface SectorSummaryRow {
  sector:         string;
  companyCount:   number;
  avgTerKe:       number | null;
  avgTerAlpha:    number | null;
  avgEpPct:       number | null;
  attractiveness: "High" | "Medium" | "Low";
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Map raw API company list to local CompanyInfo[] */
export function mapApiCompanies(raw: ApiCompany[]): CompanyInfo[] {
  return raw.map(c => ({
    ticker:   c.ticker,
    name:     c.company_name,
    sector:   c.sector,
    exchange: c.exchange,
  }));
}

/**
 * For a flat MetricResultItem[], return a map of ticker → latest non-null value.
 * "Latest" = highest fiscal_year with a non-null value.
 */
export type TickerLatestMap = Record<string, number | null>;

export function buildLatestByTicker(items: MetricResultItem[]): TickerLatestMap {
  const byTicker: Record<string, { year: number; value: number }[]> = {};
  items.forEach(r => {
    if (r.value === null) return;
    if (!byTicker[r.ticker]) byTicker[r.ticker] = [];
    byTicker[r.ticker].push({ year: r.fiscal_year, value: r.value });
  });
  const out: TickerLatestMap = {};
  Object.entries(byTicker).forEach(([ticker, pts]) => {
    pts.sort((a, b) => b.year - a.year);
    out[ticker] = pts[0]?.value ?? null;
  });
  return out;
}

/** Derive EP cohort from TER-Ke (decimal scale) */
function deriveEpCohort(terKe: number | null): EpCohort {
  if (terKe === null) return "Middle Group";
  if (terKe > 0.02)  return "EP Dominant";
  if (terKe < -0.02) return "EPS Dominant";
  return "Middle Group";
}

/**
 * Join CompanyInfo[] with four TickerLatestMaps to produce CompanyMetricRow[].
 * One row per company — no company is dropped even if all metrics are null.
 */
export function buildCompanyMetricRows(
  companies: CompanyInfo[],
  terKeMap:    TickerLatestMap,
  terAlphaMap: TickerLatestMap,
  epPctMap:    TickerLatestMap,
  tsrMap:      TickerLatestMap,
): CompanyMetricRow[] {
  return companies.map(c => {
    const terKe    = terKeMap[c.ticker]    ?? null;
    const terAlpha = terAlphaMap[c.ticker] ?? null;
    const epPct    = epPctMap[c.ticker]    ?? null;
    const tsr      = tsrMap[c.ticker]      ?? null;
    return {
      ticker:   c.ticker,
      name:     c.name,
      sector:   c.sector,
      terKe,
      terAlpha,
      epPct,
      tsr,
      cohort: deriveEpCohort(terKe),
    };
  });
}

/** Aggregate CompanyMetricRow[] by sector */
export function buildSectorSummary(rows: CompanyMetricRow[]): SectorSummaryRow[] {
  const bySector: Record<string, CompanyMetricRow[]> = {};
  rows.forEach(r => {
    if (!bySector[r.sector]) bySector[r.sector] = [];
    bySector[r.sector].push(r);
  });

  return Object.entries(bySector)
    .map(([sector, sRows]) => {
      const avg = (vals: (number | null)[]) => {
        const nonNull = vals.filter((v): v is number => v !== null);
        return nonNull.length ? nonNull.reduce((a, b) => a + b, 0) / nonNull.length : null;
      };
      const avgTerKe    = avg(sRows.map(r => r.terKe));
      const avgTerAlpha = avg(sRows.map(r => r.terAlpha));
      const avgEpPct    = avg(sRows.map(r => r.epPct));
      const attractiveness: "High" | "Medium" | "Low" =
        avgTerKe !== null && avgTerKe > 0.03 ? "High" :
        avgTerKe !== null && avgTerKe > 0    ? "Medium" : "Low";
      return { sector, companyCount: sRows.length, avgTerKe, avgTerAlpha, avgEpPct, attractiveness };
    })
    .sort((a, b) => a.sector.localeCompare(b.sector));
}
