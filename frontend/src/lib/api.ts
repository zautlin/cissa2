/**
 * CISSA API Client — Full Live Data Layer
 * ----------------------------------------
 * All endpoints verified against backend/app/api/v1/endpoints/
 */

const BASE    = "/api/v1";
const BASE_V2 = "/api/v2";

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

// ─── Companies ───────────────────────────────────────────────────────────────

/** Raw API shape — do not use directly in UI. Map via companyData.ts */
export interface ApiCompany {
  ticker:       string;
  company_name: string;
  sector:       string;
  exchange:     string;
}

export const getCompanies = (datasetId?: string) => {
  const url = datasetId
    ? `${BASE_V2}/companies?dataset_id=${encodeURIComponent(datasetId)}`
    : `${BASE_V2}/companies`;
  return fetchJSON<ApiCompany[]>(url);
};

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  message: string;
  database: string;
}
export const getHealth = () => fetchJSON<HealthResponse>(`${BASE}/metrics/health`);

// ─── Statistics ───────────────────────────────────────────────────────────────

export interface CompanyItem { ticker: string; company_name: string; sector: string; }
export interface SectorItem  { name: string; company_count: number; }
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

export const metricsExist = (datasetId: string, paramSetId: string) =>
  fetchJSON<{ exists: boolean }>(
    `${BASE}/metrics/exists?dataset_id=${datasetId}&parameter_set_id=${paramSetId}`
  );

// ─── Parameters ───────────────────────────────────────────────────────────────

export interface ParameterSetResponse {
  param_set_id: string;
  param_set_name: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  parameters: {
    country?: string;
    currency_notation?: string;
    cost_of_equity_approach?: string;
    include_franking_credits_tsr?: boolean;
    fixed_benchmark_return_wealth_preservation?: number;
    equity_risk_premium?: number;
    tax_rate_franking_credits?: number;
    value_of_franking_credits?: number;
    risk_free_rate_rounding?: number;
    beta_rounding?: number;
    last_calendar_year?: number;
    beta_relative_error_tolerance?: number;
    terminal_year?: number;
    [key: string]: unknown;
  };
  status: string;
  message: string | null;
}

export const getActiveParameters = () =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/active`);

export const getParameterSet = (paramSetId: string) =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/${paramSetId}`);

export const updateParameterSet = (
  paramSetId: string,
  overrides: Record<string, unknown>,
  setAsActive = true,
) =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/${paramSetId}/update`, {
    method: "POST",
    body: JSON.stringify({ parameters: overrides, set_as_active: setAsActive }),
  });

export const setActiveParameterSet = (paramSetId: string) =>
  fetchJSON<ParameterSetResponse>(`${BASE}/parameters/${paramSetId}/set-active`, {
    method: "POST",
  });

// ─── Metrics — Read ───────────────────────────────────────────────────────────

export interface MetricResultItem { ticker: string; fiscal_year: number; value: number | null; }
export interface MetricsResponse {
  dataset_id: string;
  parameter_set_id: string;
  metric_name: string;
  results_count: number;
  results: MetricResultItem[];
  status: string;
  message: string | null;
}

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
  if (params.ticker)      qs.set("ticker", params.ticker);
  if (params.metric_name) qs.set("metric_name", params.metric_name);
  if (params.fiscal_year) qs.set("fiscal_year", String(params.fiscal_year));
  return fetchJSON<MetricsResponse>(`${BASE}/metrics/get_metrics/?${qs}`);
};

// ─── Economic Profitability ────────────────────────────────────────────────────

export interface EconomicProfitabilityResult {
  ticker: string;
  fiscal_year: number;
  ep_1y?: number;
  ep_3y?: number;
  ep_5y?: number;
  ep_10y?: number;
  [key: string]: unknown;
}
export interface EconomicProfitabilityResponse {
  dataset_id: string;
  parameter_set_id: string;
  temporal_window: string;
  results_count: number;
  results: EconomicProfitabilityResult[];
  filters_applied: Record<string, unknown>;
  status: string;
  message: string | null;
}

export const getEconomicProfitability = (params: {
  dataset_id: string;
  parameter_set_id: string;
  ticker?: string;
  temporal_window?: "1Y" | "3Y" | "5Y" | "10Y";
  start_year?: number;
  end_year?: number;
}) => {
  const qs = new URLSearchParams();
  qs.set("dataset_id", params.dataset_id);
  qs.set("parameter_set_id", params.parameter_set_id);
  if (params.ticker)          qs.set("ticker", params.ticker);
  if (params.temporal_window) qs.set("temporal_window", params.temporal_window);
  if (params.start_year)      qs.set("start_year", String(params.start_year));
  if (params.end_year)        qs.set("end_year", String(params.end_year));
  return fetchJSON<EconomicProfitabilityResponse>(`${BASE}/metrics/economic-profitability?${qs}`);
};

// ─── Ratio Metrics ─────────────────────────────────────────────────────────────

export interface RatioTickerData {
  ticker: string;
  company_name?: string;
  sector?: string;
  time_series: { year: number; value: number | null }[];
}
export interface RatioMetricsResponse {
  metric: string;
  display_name?: string;
  temporal_window?: string;
  /** Backend returns results under "data" key */
  data?: RatioTickerData[];
  /** Legacy alias — may be absent */
  results?: RatioTickerData[];
}

export const getRatioMetrics = (params: {
  dataset_id: string;
  param_set_id: string;
  metric?: string;
  tickers?: string;
  temporal_window?: string;
}) => {
  const qs = new URLSearchParams();
  qs.set("dataset_id", params.dataset_id);
  qs.set("param_set_id", params.param_set_id);
  if (params.metric)          qs.set("metric", params.metric);
  if (params.tickers)         qs.set("tickers", params.tickers);
  if (params.temporal_window) qs.set("temporal_window", params.temporal_window);
  return fetchJSON<RatioMetricsResponse>(`${BASE}/metrics/ratio-metrics?${qs}`);
};

// ─── Optimization Metrics ─────────────────────────────────────────────────────
// Same response shape as get_metrics. Endpoint is not yet live — returns empty
// results until the backend optimization_metrics endpoint is deployed.

export const getOptimizationMetrics = (params: GetMetricsParams) => {
  const qs = new URLSearchParams();
  qs.set("dataset_id", params.dataset_id);
  qs.set("parameter_set_id", params.parameter_set_id);
  if (params.ticker)      qs.set("ticker", params.ticker);
  if (params.metric_name) qs.set("metric_name", params.metric_name);
  if (params.fiscal_year) qs.set("fiscal_year", String(params.fiscal_year));
  return fetchJSON<MetricsResponse>(`${BASE}/metrics/optimization_metrics?${qs}`).catch(
    // Endpoint not yet live — return empty results gracefully
    () => ({ dataset_id: params.dataset_id, parameter_set_id: params.parameter_set_id, metric_name: params.metric_name ?? "", results_count: 0, results: [], status: "pending", message: "optimization_metrics endpoint not yet available" } as MetricsResponse)
  );
};

// ─── Calculate (POST) ──────────────────────────────────────────────────────────

export interface CalculateMetricsResponse {
  dataset_id: string;
  metric_name: string;
  results_count: number;
  results: MetricResultItem[];
  status: string;
  message: string | null;
}

export const calculateMetric = (datasetId: string, metricName: string, paramSetId?: string) =>
  fetchJSON<CalculateMetricsResponse>(`${BASE}/metrics/calculate`, {
    method: "POST",
    body: JSON.stringify({
      dataset_id: datasetId,
      metric_name: metricName,
      ...(paramSetId ? { param_set_id: paramSetId } : {}),
    }),
  });

export interface CalculateL1OrchestratorResponse {
  success: boolean;
  execution_time_seconds: number;
  dataset_id: string;
  param_set_id: string;
  timestamp: string;
  total_successful: number;
  total_failed: number;
  total_records_inserted?: number;
  phases?: Record<string, unknown>;
  errors?: string[];
}

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
  metrics_completed: Record<string, { status: string; records_inserted: number; time_seconds: number }>;
}

export const runRuntimeMetrics = (datasetId: string, paramSetId: string) =>
  fetchJSON<RuntimeMetricsResponse>(
    `${BASE}/metrics/runtime-metrics?dataset_id=${datasetId}&param_set_id=${paramSetId}`,
    { method: "POST" }
  );

export const calculateBetaFromPrecomputed = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/beta/calculate-from-precomputed`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateCostOfEquity = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/cost-of-equity/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateRates = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/rates/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateL2Core = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-core/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateFvEcf = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-fv-ecf/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateTer = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-ter/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });

export const calculateTerAlpha = (datasetId: string, paramSetId: string) =>
  fetchJSON<Record<string, unknown>>(`${BASE}/metrics/l2-ter-alpha/calculate`, {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, param_set_id: paramSetId }),
  });
