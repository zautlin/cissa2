/**
 * useMetrics — Central live-data hook for CISSA dashboard
 *
 * Pattern:
 *   1. Always fetch /api/v1/parameters/active first to get dataset_id + param_set_id
 *   2. Use those IDs to query any downstream endpoint
 *   3. Falls back gracefully: if no data, returns null so pages show skeleton states
 */
import { useState, useEffect, useCallback } from "react";
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
        // 1. Get active params
        const paramResponse = await getActiveParameters();
        if (cancelled) return;

        const paramSetId = paramResponse.param_set_id;

        // 2. Get all dataset stats to find a dataset_id
        const statsAll = await getStatistics() as Record<string, DatasetStatistics>;
        if (cancelled) return;

        const keys = Object.keys(statsAll);
        if (keys.length === 0) {
          setCtx(c => ({ ...c, loading: false, params: paramResponse.parameters,
            paramSetId, error: null }));
          return;
        }

        const datasetId = keys[0];
        const stats = statsAll[datasetId];

        // 3. Check if metrics exist
        let hasMetrics = false;
        try {
          const ex = await metricsExist(datasetId, paramSetId);
          hasMetrics = ex.exists;
        } catch (_) { /* backend might not have data yet */ }

        if (!cancelled) {
          setCtx({
            datasetId, paramSetId,
            params: paramResponse.parameters,
            stats,
            hasMetrics,
            loading: false,
            error: null,
          });
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

// ─── useRatioMetric ────────────────────────────────────────────────────────────

export function useRatioMetric(
  datasetId: string | null,
  paramSetId: string | null,
  metric: string,
  temporalWindow?: string
) {
  const [state, setState] = useState<{ data: any; loading: boolean; error: string | null }>({
    data: null, loading: false, error: null,
  });

  useEffect(() => {
    if (!datasetId || !paramSetId) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    getRatioMetrics({ dataset_id: datasetId, param_set_id: paramSetId, metric, temporal_window: temporalWindow })
      .then(r => { if (!cancelled) setState({ data: r, loading: false, error: null }); })
      .catch(e => { if (!cancelled) setState({ data: null, loading: false, error: e.message }); });
    return () => { cancelled = true; };
  }, [datasetId, paramSetId, metric, temporalWindow]);

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

// ─── Helper: group metric results by ticker ───────────────────────────────────
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
      value: vals.sort((a, b) => a - b)[Math.floor(vals.length / 2)], // median
    }))
    .sort((a, b) => a.year - b.year);
}
