/**
 * useMetrics — Central live-data hook for CISSA dashboard
 *
 * FIXED: useRatioMetric now returns normalized flat array:
 *   { ticker, company_name, sector, value, time_series }[]
 *   where `value` = the most recent non-null value from time_series
 *
 * Pattern:
 *   1. Always fetch /api/v1/parameters/active first to get dataset_id + param_set_id
 *   2. Use those IDs to query any downstream endpoint
 *   3. Falls back gracefully: if no data, returns null so pages show skeleton states
 */
import { useState, useEffect } from "react";
import {
  getActiveParameters,
  getStatistics,
  getMetrics,
  getEconomicProfitability,
  getRatioMetrics,
  metricsExist,
  ParameterSetResponse,
  DatasetStatistics,
  MetricResultItem,
  EconomicProfitabilityResult,
  RatioTickerData,
} from "../lib/api";

// ─── Active context ────────────────────────────────────────────────────────────

export interface ActiveContext {
  datasetId: string | null;
  paramSetId: string | null;
  params: ParameterSetResponse["parameters"] | null;
  stats: DatasetStatistics | null;
  hasMetrics: boolean;
  loading: boolean;
  error: string | null;
}

export function useActiveContext(): ActiveContext {
  const [ctx, setCtx] = useState<ActiveContext>({
    datasetId: null, paramSetId: null,
    params: null, stats: null,
    hasMetrics: false, loading: true, error: null,
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const paramResponse = await getActiveParameters();
        if (cancelled) return;

        const paramSetId = paramResponse.param_set_id;

        const statsAll = await getStatistics() as Record<string, DatasetStatistics>;
        if (cancelled) return;

        const keys = Object.keys(statsAll);
        if (keys.length === 0) {
          setCtx(c => ({ ...c, loading: false, params: paramResponse.parameters, paramSetId, error: null }));
          return;
        }

        const datasetId = keys[0];
        const stats = statsAll[datasetId];

        let hasMetrics = false;
        try {
          const ex = await metricsExist(datasetId, paramSetId);
          hasMetrics = ex.exists;
        } catch (_) { /* backend might not have data yet */ }

        if (!cancelled) {
          setCtx({ datasetId, paramSetId, params: paramResponse.parameters, stats, hasMetrics, loading: false, error: null });
        }
      } catch (err: any) {
        if (!cancelled) {
          setCtx(c => ({ ...c, loading: false, error: err.message || "API error" }));
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return ctx;
}

// ─── Normalized ratio item ──────────────────────────────────────────────────────

export interface NormalizedRatioItem {
  ticker: string;
  company_name: string;
  sector: string;
  /** Most recent non-null value from time_series */
  value: number | null;
  /** Full time series [{year, value}] for sparklines/drill-down */
  time_series: { year: number; value: number | null }[];
}

function normalizeRatioResults(results: RatioTickerData[]): NormalizedRatioItem[] {
  return results.map(r => {
    const ts = r.time_series ?? [];
    // Most recent non-null value
    const nonNull = ts.filter(t => t.value !== null);
    const latest = nonNull.length ? nonNull[nonNull.length - 1].value : null;
    return {
      ticker: r.ticker,
      company_name: r.company_name ?? r.ticker,
      sector: r.sector ?? "Unknown",
      value: latest,
      time_series: ts,
    };
  });
}

// ─── useRatioMetric ─────────────────────────────────────────────────────────────

export interface RatioMetricState {
  data: NormalizedRatioItem[];
  raw: RatioTickerData[];
  loading: boolean;
  error: string | null;
}

export function useRatioMetric(
  datasetId: string | null,
  paramSetId: string | null,
  metric: string,
  temporalWindow?: string
): RatioMetricState {
  const [state, setState] = useState<RatioMetricState>({
    data: [], raw: [], loading: false, error: null,
  });

  useEffect(() => {
    if (!datasetId || !paramSetId) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    getRatioMetrics({ dataset_id: datasetId, param_set_id: paramSetId, metric, temporal_window: temporalWindow })
      .then(r => {
        if (!cancelled) {
          const normalized = normalizeRatioResults(r.results ?? []);
          setState({ data: normalized, raw: r.results ?? [], loading: false, error: null });
        }
      })
      .catch(e => { if (!cancelled) setState({ data: [], raw: [], loading: false, error: e.message }); });
    return () => { cancelled = true; };
  }, [datasetId, paramSetId, metric, temporalWindow]);

  return state;
}

// ─── useMetricSeries — fetch a single named metric over all tickers/years ───

export interface MetricSeriesState {
  data: MetricResultItem[];
  loading: boolean;
  error: string | null;
}

export function useMetricSeries(
  datasetId: string | null,
  paramSetId: string | null,
  metricName: string,
  ticker?: string
): MetricSeriesState {
  const [state, setState] = useState<MetricSeriesState>({ data: [], loading: false, error: null });

  useEffect(() => {
    if (!datasetId || !paramSetId) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: metricName, ticker })
      .then(r => { if (!cancelled) setState({ data: r.results, loading: false, error: null }); })
      .catch(e => { if (!cancelled) setState({ data: [], loading: false, error: e.message }); });
    return () => { cancelled = true; };
  }, [datasetId, paramSetId, metricName, ticker]);

  return state;
}

// ─── useEPSeries — EP Bow Wave data ────────────────────────────────────────

export interface EPSeriesState {
  data: EconomicProfitabilityResult[];
  loading: boolean;
  error: string | null;
}

export function useEPSeries(
  datasetId: string | null,
  paramSetId: string | null,
  window: "1Y" | "3Y" | "5Y" | "10Y" = "1Y",
  ticker?: string
): EPSeriesState {
  const [state, setState] = useState<EPSeriesState>({ data: [], loading: false, error: null });

  useEffect(() => {
    if (!datasetId || !paramSetId) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    getEconomicProfitability({ dataset_id: datasetId, parameter_set_id: paramSetId, temporal_window: window, ticker })
      .then(r => { if (!cancelled) setState({ data: r.results, loading: false, error: null }); })
      .catch(e => { if (!cancelled) setState({ data: [], loading: false, error: e.message }); });
    return () => { cancelled = true; };
  }, [datasetId, paramSetId, window, ticker]);

  return state;
}

// ─── useMultipleMetrics — batch fetch several metric names ───────────────────

export function useMultipleMetrics(
  datasetId: string | null,
  paramSetId: string | null,
  metricNames: string[]
): { data: Record<string, MetricResultItem[]>; loading: boolean; error: string | null } {
  const [state, setState] = useState<{
    data: Record<string, MetricResultItem[]>; loading: boolean; error: string | null
  }>({ data: {}, loading: false, error: null });

  useEffect(() => {
    if (!datasetId || !paramSetId || metricNames.length === 0) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));

    const promises = metricNames.map(name =>
      getMetrics({ dataset_id: datasetId, parameter_set_id: paramSetId, metric_name: name })
        .then(r => ({ name, results: r.results }))
        .catch(() => ({ name, results: [] as MetricResultItem[] }))
    );

    Promise.all(promises).then(results => {
      if (cancelled) return;
      const data: Record<string, MetricResultItem[]> = {};
      results.forEach(({ name, results: r }) => { data[name] = r; });
      setState({ data, loading: false, error: null });
    });

    return () => { cancelled = true; };
  }, [datasetId, paramSetId, metricNames.join(",")]);

  return state;
}

// ─── Helper: aggregate EP to annual index series ──────────────────────────────
export function aggregateEPToIndex(epData: EconomicProfitabilityResult[]): { year: number; ep: number }[] {
  const byYear: Record<number, number[]> = {};
  epData.forEach(r => {
    const val = r.ep_1y ?? r.ep_3y ?? r.ep_5y ?? r.ep_10y ?? null;
    if (val !== null) {
      if (!byYear[r.fiscal_year]) byYear[r.fiscal_year] = [];
      byYear[r.fiscal_year].push(val);
    }
  });
  return Object.entries(byYear)
    .map(([y, vals]) => ({ year: Number(y), ep: vals.reduce((a, b) => a + b, 0) / vals.length }))
    .sort((a, b) => a.year - b.year);
}

// ─── Helper: group MetricResultItem[] by ticker ───────────────────────────────
export function groupByTicker(data: MetricResultItem[]): Record<string, { year: number; value: number }[]> {
  const out: Record<string, { year: number; value: number }[]> = {};
  data.forEach(r => {
    if (r.value === null) return;
    if (!out[r.ticker]) out[r.ticker] = [];
    out[r.ticker].push({ year: r.fiscal_year, value: r.value });
  });
  Object.values(out).forEach(arr => arr.sort((a, b) => a.year - b.year));
  return out;
}

// ─── Helper: aggregate across all tickers by year (median) ───────────────────
export function aggregateByYear(data: MetricResultItem[]): { year: number; value: number }[] {
  const byYear: Record<number, number[]> = {};
  data.forEach(r => {
    if (r.value !== null) {
      if (!byYear[r.fiscal_year]) byYear[r.fiscal_year] = [];
      byYear[r.fiscal_year].push(r.value);
    }
  });
  return Object.entries(byYear)
    .map(([y, vals]) => ({
      year: Number(y),
      value: vals.sort((a, b) => a - b)[Math.floor(vals.length / 2)],
    }))
    .sort((a, b) => a.year - b.year);
}

// ─── Helper: get flat {ticker, value, sector, company_name} from NormalizedRatioItem[] ─
export function ratioToFlat(data: NormalizedRatioItem[]): { ticker: string; value: number; sector: string; company_name: string }[] {
  return data
    .filter(r => r.value !== null && !isNaN(r.value as number))
    .map(r => ({ ticker: r.ticker, value: r.value as number, sector: r.sector, company_name: r.company_name }));
}

// ─── Helper: group NormalizedRatioItem[] by sector ───────────────────────────
export function groupRatioBySector(data: NormalizedRatioItem[]): Record<string, NormalizedRatioItem[]> {
  const out: Record<string, NormalizedRatioItem[]> = {};
  data.forEach(r => {
    const s = r.sector || "Unknown";
    if (!out[s]) out[s] = [];
    out[s].push(r);
  });
  return out;
}
