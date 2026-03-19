/**
 * CISSA API Client
 * ----------------
 * Thin wrapper around the FastAPI backend at /api/v1/
 * All endpoints match the existing backend routes exactly — no backend changes needed.
 *
 * Base URL is relative so it works in both dev (Vite proxy → localhost:8000)
 * and production (same-origin serving).
 */

const BASE = "/api/v1";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Health ────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  message: string;
  database: string;
}

export const getHealth = () =>
  fetchJSON<HealthResponse>(`${BASE}/metrics/health`);

// ─── Statistics (companies, sectors, coverage) ─────────────────────────────

export interface CompanyItem {
  ticker: string;
  company_name: string;
  sector: string;
}

export interface SectorItem {
  name: string;
  company_count: number;
}

export interface DatasetStatistics {
  dataset_id: string;
  dataset_created_at: string;
  country: string;
  companies: { count: number; items: CompanyItem[] };
  sectors: { count: number; items: SectorItem[] };
  data_coverage: { min_year: number; max_year: number };
  raw_metrics: { count: number };
}

export const getStatistics = (datasetId?: string) => {
  const url = datasetId
    ? `${BASE}/metrics/statistics?dataset_id=${datasetId}`
    : `${BASE}/metrics/statistics`;
  return fetchJSON<DatasetStatistics | Record<string, DatasetStatistics>>(url);
};

// ─── Parameters ────────────────────────────────────────────────────────────

export interface ParameterSetResponse {
  param_set_id: string;
  param_set_name: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  parameters: Record<string, unknown>;
  status: string;
  message: string | null;
}

export const getActiveParameters = () =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/active`);

export const getParameterSet = (paramSetId: string) =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/${paramSetId}`);

// ─── Metrics ───────────────────────────────────────────────────────────────

export interface MetricResultItem {
  ticker: string;
  fiscal_year: number;
  value: number | null;
}

export interface MetricsResponse {
  dataset_id: string;
  metric_name: string;
  results_count: number;
  results: MetricResultItem[];
  status: string;
  message: string | null;
}

/** POST /api/v1/metrics/calculate */
export const calculateMetric = (
  datasetId: string,
  metricName: string,
  paramSetId?: string
) =>
  fetchJSON<MetricsResponse>(`${BASE}/metrics/calculate`, {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      metric_name: metricName,
      ...(paramSetId ? { param_set_id: paramSetId } : {}),
    }),
  });

/** GET /api/v1/metrics/get_metrics/ */
export interface GetMetricsParams {
  dataset_id: string;
  parameter_set_id: string;
  ticker?: string;
  metric_name?: string;
  fiscal_year?: number;
}

export const getMetrics = (params: GetMetricsParams) => {
  const qs = new URLSearchParams();
  qs.set("dataset_id", params.dataset_id);
  qs.set("parameter_set_id", params.parameter_set_id);
  if (params.ticker) qs.set("ticker", params.ticker);
  if (params.metric_name) qs.set("metric_name", params.metric_name);
  if (params.fiscal_year) qs.set("fiscal_year", String(params.fiscal_year));
  return fetchJSON<MetricsResponse>(`${BASE}/metrics/get_metrics/?${qs}`);
};

// ─── Ratio Metrics ─────────────────────────────────────────────────────────

export interface RatioMetricsResponse {
  dataset_id: string;
  param_set_id: string;
  window: string;
  results: MetricResultItem[];
  status: string;
}

export const getRatioMetrics = (datasetId: string, paramSetId: string) =>
  fetchJSON<RatioMetricsResponse>(
    `${BASE}/metrics/ratio-metrics?dataset_id=${datasetId}&param_set_id=${paramSetId}`
  );

// ─── Cost of Equity ────────────────────────────────────────────────────────

export interface EnhancedMetricsResponse {
  dataset_id: string;
  param_set_id: string;
  value: number;
  metrics_calculated: string[];
  status: string;
  timestamp: string;
  message: string;
}

export const calculateCostOfEquity = (
  datasetId: string,
  paramSetId: string
) =>
  fetchJSON<EnhancedMetricsResponse>(
    `${BASE}/metrics/cost-of-equity/calculate`,
    {
      method: "POST",
      body: JSON.stringify({
        dataset_id: datasetId,
        param_set_id: paramSetId,
      }),
    }
  );

// ─── Orchestration ─────────────────────────────────────────────────────────

export interface OrchestrateResponse {
  status: string;
  message: string;
  dataset_id: string;
  param_set_id: string;
}

export const orchestrateL1Metrics = (
  datasetId: string,
  paramSetId: string
) =>
  fetchJSON<OrchestrateResponse>(`${BASE}/orchestration/l1`, {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      param_set_id: paramSetId,
    }),
  });
