/**
 * CISSA API Client
 * ----------------
 * Typed wrapper around the FastAPI backend at /api/v1/
 *
 * Endpoint map (all verified against backend/app/api/v1/endpoints/):
 *
 *   GET  /api/v1/metrics/health
 *   GET  /api/v1/metrics/statistics[?dataset_id=]
 *   GET  /api/v1/metrics/exists?dataset_id=&parameter_set_id=
 *   GET  /api/v1/metrics/get_metrics/?dataset_id=&parameter_set_id=[&ticker=][&metric_name=]
 *   GET  /api/v1/metrics/ratio-metrics?dataset_id=&param_set_id=
 *   GET  /api/v1/metrics/economic-profitability?dataset_id=&parameter_set_id=[&ticker=][&temporal_window=]
 *   POST /api/v1/metrics/calculate             body: {dataset_id, metric_name, param_set_id?}
 *   POST /api/v1/metrics/calculate-l2          body: {dataset_id, param_set_id}
 *   POST /api/v1/metrics/beta/calculate-from-precomputed
 *   POST /api/v1/metrics/cost-of-equity/calculate  body: {dataset_id, param_set_id}
 *   POST /api/v1/metrics/rates/calculate
 *   POST /api/v1/metrics/l2-core/calculate
 *   POST /api/v1/metrics/l2-fv-ecf/calculate
 *   POST /api/v1/metrics/l2-ter/calculate
 *   POST /api/v1/metrics/l2-ter-alpha/calculate
 *   POST /api/v1/metrics/calculate-l1          body: {dataset_id, param_set_id}  ← L1 pre-computation orchestrator
 *   POST /api/v1/metrics/runtime-metrics?dataset_id=&param_set_id=              ← Phase 3+ full orchestrator
 *   GET  /api/v1/parameters/active
 *   GET  /api/v1/parameters/{param_set_id}
 *
 * Base URL is relative: works in dev (Vite proxy → localhost:8000)
 * and production (same-origin serving behind nginx/uvicorn StaticFiles).
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

// ─── Health ─────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  message: string;
  database: string;
}

/** GET /api/v1/metrics/health */
export const getHealth = () =>
  fetchJSON<HealthResponse>(`${BASE}/metrics/health`);

// ─── Statistics ──────────────────────────────────────────────────────────────

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

/**
 * GET /api/v1/metrics/statistics
 * - No params → returns all datasets keyed by dataset_id
 * - ?dataset_id=<uuid> → returns single DatasetStatistics
 */
export const getStatistics = (datasetId?: string) => {
  const url = datasetId
    ? `${BASE}/metrics/statistics?dataset_id=${datasetId}`
    : `${BASE}/metrics/statistics`;
  return fetchJSON<DatasetStatistics | Record<string, DatasetStatistics>>(url);
};

/**
 * GET /api/v1/metrics/exists?dataset_id=&parameter_set_id=
 */
export const metricsExist = (datasetId: string, paramSetId: string) =>
  fetchJSON<{ exists: boolean }>(
    `${BASE}/metrics/exists?dataset_id=${datasetId}&parameter_set_id=${paramSetId}`
  );

// ─── Parameters ──────────────────────────────────────────────────────────────

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

/** GET /api/v1/parameters/active */
export const getActiveParameters = () =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/active`);

/** GET /api/v1/parameters/{param_set_id} */
export const getParameterSet = (paramSetId: string) =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/${paramSetId}`);

// ─── Metrics — Read ──────────────────────────────────────────────────────────

export interface MetricResultItem {
  ticker: string;
  fiscal_year: number;
  value: number | null;
}

export interface MetricsResponse {
  dataset_id: string;
  parameter_set_id: string;   // note: backend uses parameter_set_id (not param_set_id) in GET response
  metric_name: string;
  results_count: number;
  results: MetricResultItem[];
  status: string;
  message: string | null;
}

/**
 * GET /api/v1/metrics/get_metrics/
 * All params required: dataset_id, parameter_set_id
 * Optional: ticker, metric_name (supports comma-separated), fiscal_year
 */
export interface GetMetricsParams {
  dataset_id: string;
  parameter_set_id: string;  // ← correct query param name per backend
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

// ─── Economic Profitability ───────────────────────────────────────────────────

export interface EconomicProfitabilityParams {
  dataset_id: string;
  parameter_set_id: string;
  ticker?: string;
  temporal_window?: "1Y" | "3Y" | "5Y" | "10Y";
  start_year?: number;
  end_year?: number;
}

/**
 * GET /api/v1/metrics/economic-profitability
 * Returns EP metrics with temporal aggregation (1Y/3Y/5Y/10Y).
 */
export const getEconomicProfitability = (params: EconomicProfitabilityParams) => {
  const qs = new URLSearchParams();
  qs.set("dataset_id", params.dataset_id);
  qs.set("parameter_set_id", params.parameter_set_id);
  if (params.ticker) qs.set("ticker", params.ticker);
  if (params.temporal_window) qs.set("temporal_window", params.temporal_window);
  if (params.start_year) qs.set("start_year", String(params.start_year));
  if (params.end_year) qs.set("end_year", String(params.end_year));
  return fetchJSON<Record<string, unknown>>(`${BASE}/metrics/economic-profitability?${qs}`);
};

// ─── Ratio Metrics ───────────────────────────────────────────────────────────

export interface RatioMetricsResponse {
  dataset_id: string;
  param_set_id: string;
  window: string;
  results: MetricResultItem[];
  status: string;
}

/**
 * GET /api/v1/metrics/ratio-metrics?dataset_id=&param_set_id=
 */
export const getRatioMetrics = (datasetId: string, paramSetId: string) =>
  fetchJSON<RatioMetricsResponse>(
    `${BASE}/metrics/ratio-metrics?dataset_id=${datasetId}&param_set_id=${paramSetId}`
  );

// ─── Metrics — Calculate (individual) ────────────────────────────────────────

export interface CalculateMetricsResponse {
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
  fetchJSON<CalculateMetricsResponse>(`${BASE}/metrics/calculate`, {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      metric_name: metricName,
      ...(paramSetId ? { param_set_id: paramSetId } : {}),
    }),
  });

/** POST /api/v1/metrics/calculate-l2 — body: {dataset_id, param_set_id} */
export const calculateL2 = (datasetId: string, paramSetId: string) =>
  fetchJSON<CalculateMetricsResponse>(`${BASE}/metrics/calculate-l2`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/l2-core/calculate */
export const calculateL2Core = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-core/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/l2-fv-ecf/calculate */
export const calculateFvEcf = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-fv-ecf/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/l2-ter/calculate */
export const calculateTer = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-ter/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/l2-ter-alpha/calculate */
export const calculateTerAlpha = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-ter-alpha/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

// ─── Beta & Cost of Equity ───────────────────────────────────────────────────

export interface EnhancedMetricsResponse {
  dataset_id: string;
  param_set_id: string;
  value?: number;
  metrics_calculated: string[];
  status: string;
  timestamp: string;
  message: string;
}

/** POST /api/v1/metrics/beta/calculate-from-precomputed */
export const calculateBetaFromPrecomputed = (datasetId: string, paramSetId: string) =>
  fetchJSON<EnhancedMetricsResponse>(`${BASE}/metrics/beta/calculate-from-precomputed`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/cost-of-equity/calculate */
export const calculateCostOfEquity = (datasetId: string, paramSetId: string) =>
  fetchJSON<EnhancedMetricsResponse>(`${BASE}/metrics/cost-of-equity/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

/** POST /api/v1/metrics/rates/calculate */
export const calculateRates = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/rates/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

// ─── Orchestration ───────────────────────────────────────────────────────────

export interface CalculateL1OrchestratorResponse {
  success: boolean;
  execution_time_seconds: number;
  dataset_id: string;
  param_set_id: string;
  timestamp: string;
  total_successful: number;
  total_failed: number;
}

/**
 * POST /api/v1/metrics/calculate-l1
 * L1 pre-computation orchestrator: parallelises Phase 1 (11 metrics in 4 groups),
 * then sequences Phase 2 (2 metrics).
 *
 * NOTE: This is NOT /api/v1/orchestration/l1 — that path does NOT exist.
 * The orchestration router prefix is /api/v1/metrics and the route is /calculate-l1.
 */
export const orchestrateL1Metrics = (
  datasetId: string,
  paramSetId: string,
  options?: { concurrency?: number; maxRetries?: number }
) =>
  fetchJSON<CalculateL1OrchestratorResponse>(`${BASE}/metrics/calculate-l1`, {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      param_set_id: paramSetId,
      ...(options?.concurrency ? { concurrency: options.concurrency } : {}),
      ...(options?.maxRetries ? { max_retries: options.maxRetries } : {}),
    }),
  });

export interface RuntimeMetricsResponse {
  success: boolean;
  execution_time_seconds: number;
  dataset_id: string;
  param_set_id: string;
  metrics_completed: Record<string, {
    status: string;
    records_inserted: number;
    time_seconds: number;
  }>;
}

/**
 * POST /api/v1/metrics/runtime-metrics?dataset_id=&param_set_id=
 * Full Phase 3+ orchestrator: Beta Rounding → Rf → Ke → FV-ECF → TER → TER Alpha.
 * This is the main "run everything" endpoint per DATABASE_AND_METRICS_WORKFLOW.md.
 */
export const runRuntimeMetrics = (datasetId: string, paramSetId: string) =>
  fetchJSON<RuntimeMetricsResponse>(
    `${BASE}/metrics/runtime-metrics?dataset_id=${datasetId}&param_set_id=${paramSetId}`,
    { method: "POST" }
  );
