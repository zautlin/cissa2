/**
 * metricRegistry.ts — Single source of truth for all metric → API endpoint mappings.
 *
 * THREE endpoint types, each with different query param names:
 *   get_metrics    → /api/v1/metrics/get_metrics/      (metric_name=, parameter_set_id=)
 *   ratio_metrics  → /api/v1/metrics/ratio-metrics     (metric=,      param_set_id=, tickers=)
 *   ep_series      → /api/v1/metrics/economic-profitability (temporal_window=, parameter_set_id=)
 *
 * Default: ticker is always included. GroupName is future-safe:
 *   - set groupType: "sector" | "index" on the MetricDef
 *   - pass groupName into buildMetricUrl — it is appended automatically
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type EndpointType = "get_metrics" | "ratio_metrics" | "ep_series";
export type GroupType    = "sector" | "index";

export interface MetricDef {
  /** Frontend identifier — use this key in all page/hook code */
  key:          string;
  /** Exact value sent to the API (metric_name or metric query param) */
  apiName:      string;
  /** API path */
  endpoint:     string;
  /** Controls which query param names are used when building the URL */
  endpointType: EndpointType;
  /** Human-readable label for chart legends / table headers */
  label:        string;
  /**
   * Future: when set, a groupName passed to buildMetricUrl is appended as
   * &sector=<groupName> or &index=<groupName>
   */
  groupType?:   GroupType;
}

// ─── Param name maps per endpoint type ───────────────────────────────────────
// Each endpoint uses slightly different query param names — centralised here.

const PARAM_NAMES: Record<EndpointType, {
  datasetId:  string;
  paramSetId: string;
  metricKey:  string;
  ticker:     string;
}> = {
  get_metrics: {
    datasetId:  "dataset_id",
    paramSetId: "parameter_set_id",
    metricKey:  "metric_name",
    ticker:     "ticker",
  },
  ratio_metrics: {
    datasetId:  "dataset_id",
    paramSetId: "param_set_id",
    metricKey:  "metric",
    ticker:     "tickers",       // ratio-metrics uses plural
  },
  ep_series: {
    datasetId:  "dataset_id",
    paramSetId: "parameter_set_id",
    metricKey:  "temporal_window", // ep_series uses window not metric_name
    ticker:     "ticker",
  },
};

// ─── URL builder ─────────────────────────────────────────────────────────────

export interface MetricUrlCtx {
  datasetId:  string;
  paramSetId: string;
  ticker:     string;
  /** Future: when provided + MetricDef.groupType is set, appended to URL */
  groupName?: string;
}

export function buildMetricUrl(def: MetricDef, ctx: MetricUrlCtx): string {
  const names = PARAM_NAMES[def.endpointType];
  const p = new URLSearchParams({
    [names.datasetId]:  ctx.datasetId,
    [names.paramSetId]: ctx.paramSetId,
    [names.metricKey]:  def.apiName,
    [names.ticker]:     ctx.ticker,
  });
  // Future-safe: group filter appended automatically when both are present
  if (ctx.groupName && def.groupType) {
    p.set(def.groupType, ctx.groupName);
  }
  return `${def.endpoint}?${p.toString()}`;
}

/** Look up a MetricDef by key — throws if not found */
export function getMetricDef(key: string): MetricDef {
  const def = METRIC_REGISTRY.find(m => m.key === key);
  if (!def) throw new Error(`metricRegistry: unknown metric key "${key}"`);
  return def;
}

// ─── Registry ─────────────────────────────────────────────────────────────────
// Organised by endpoint type then logical group.

export const METRIC_REGISTRY: MetricDef[] = [

  // ── get_metrics — L1 (pre-computed SQL) ────────────────────────────────────
  { key: "mc",            apiName: "Calc MC",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Market Capitalisation"        },
  { key: "assets",        apiName: "Calc Assets",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Total Assets"                  },
  { key: "oa",            apiName: "Calc OA",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Other Assets"                  },
  { key: "op_cost",       apiName: "Calc Op Cost",       endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Operating Cost"                },
  { key: "non_op_cost",   apiName: "Calc Non Op Cost",   endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Non-Operating Cost"            },
  { key: "tax_cost",      apiName: "Calc Tax Cost",      endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Tax Cost"                      },
  { key: "xo_cost",       apiName: "Calc XO Cost",       endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Extraordinary Cost"            },
  { key: "ecf",           apiName: "Calc ECF",           endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Equity Cash Flow"              },
  { key: "non_div_ecf",   apiName: "Non Div ECF",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Non-Dividend ECF"              },
  { key: "ee",            apiName: "Calc EE",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Economic Equity"               },
  { key: "tsr",           apiName: "Calc FY TSR",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Total Shareholder Return"      },
  { key: "tsr_prel",      apiName: "Calc FY TSR PREL",   endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TSR Preliminary"               },

  // ── get_metrics — Runtime Phase 07–09 ──────────────────────────────────────
  { key: "beta",          apiName: "Calc Beta",          endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Equity Beta"                   },
  { key: "rf",            apiName: "Calc Rf",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Risk-Free Rate"                },
  { key: "ke",            apiName: "Calc Ke",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Cost of Equity"                },

  // ── get_metrics — L2 Core (Phase 10a) ──────────────────────────────────────
  { key: "ep",            apiName: "Calc EP",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Economic Profit"               },
  { key: "ep_pct",        apiName: "EP PCT",             endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Economic Profit Margin"        },
  { key: "pat_ex",        apiName: "Calc PAT_Ex",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Profit After Tax"              },
  { key: "xo_cost_ex",    apiName: "Calc XO_Cost_Ex",    endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "XO Cost Ex"                    },
  { key: "fc",            apiName: "Calc FC",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Free Cash Flow"                },
  { key: "trte",          apiName: "TRTE",               endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Total Return to Equity"        },
  { key: "ra_mm",         apiName: "RA MM",              endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Return on Assets (Market)"     },
  { key: "ter",           apiName: "TER",                endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Total Economic Return"         },
  { key: "ter_ke",        apiName: "TER-Ke",             endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Spread (TER - Ke)"         },
  { key: "tera",          apiName: "TERA",               endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Alpha"                     },
  { key: "wc_tera",       apiName: "WC TERA",            endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "Working Capital TER Alpha"     },

  // ── get_metrics — FV-ECF (Phase 10b) ───────────────────────────────────────
  { key: "fv_ecf_1y",     apiName: "Calc 1Y FV ECF",    endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "FV-ECF 1Y"                     },
  { key: "fv_ecf_3y",     apiName: "Calc 3Y FV ECF",    endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "FV-ECF 3Y"                     },
  { key: "fv_ecf_5y",     apiName: "Calc 5Y FV ECF",    endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "FV-ECF 5Y"                     },
  { key: "fv_ecf_10y",    apiName: "Calc 10Y FV ECF",   endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "FV-ECF 10Y"                    },

  // ── get_metrics — TER windowed (Phase 10c) ──────────────────────────────────
  { key: "ter_1y",        apiName: "Calc 1Y TER",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER 1Y"                        },
  { key: "ter_3y",        apiName: "Calc 3Y TER",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER 3Y"                        },
  { key: "ter_5y",        apiName: "Calc 5Y TER",        endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER 5Y"                        },
  { key: "ter_10y",       apiName: "Calc 10Y TER",       endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER 10Y"                       },
  { key: "ter_ke_1y",     apiName: "Calc 1Y TER-KE",     endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER-Ke 1Y"                     },
  { key: "ter_ke_3y",     apiName: "Calc 3Y TER-KE",     endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER-Ke 3Y"                     },
  { key: "ter_ke_5y",     apiName: "Calc 5Y TER-KE",     endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER-Ke 5Y"                     },
  { key: "ter_ke_10y",    apiName: "Calc 10Y TER-KE",    endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER-Ke 10Y"                    },
  { key: "ter_alpha_1y",  apiName: "Calc 1Y TER Alpha",  endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Alpha 1Y"                  },
  { key: "ter_alpha_3y",  apiName: "Calc 3Y TER Alpha",  endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Alpha 3Y"                  },
  { key: "ter_alpha_5y",  apiName: "Calc 5Y TER Alpha",  endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Alpha 5Y"                  },
  { key: "ter_alpha_10y", apiName: "Calc 10Y TER Alpha", endpoint: "/api/v1/metrics/get_metrics/", endpointType: "get_metrics", label: "TER Alpha 10Y"                 },

  // ── ratio_metrics — time-series ratios ─────────────────────────────────────
  { key: "ratio_mb",              apiName: "mb_ratio",          endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "M:B Ratio"                    },
  { key: "ratio_roee",            apiName: "roee",              endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Return on Economic Equity"    },
  { key: "ratio_roa",             apiName: "roa",               endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Return on Assets"             },
  { key: "ratio_profit_margin",   apiName: "profit_margin",     endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Profit Margin"                },
  { key: "ratio_op_cost_margin",  apiName: "op_cost_margin",    endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Op Cost Margin"               },
  { key: "ratio_non_op_margin",    apiName: "non_op_cost_margin", endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Non-Op Cost Margin"          },
  { key: "ratio_etr",              apiName: "etr",                endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Effective Tax Rate"          },
  { key: "ratio_xo_cost_margin",  apiName: "xo_cost_margin",    endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "XO Cost Margin"               },
  { key: "ratio_fa_intensity",    apiName: "fa_intensity",      endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Fixed Asset Intensity"        },
  { key: "ratio_gw_intensity",    apiName: "gw_intensity",      endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Goodwill Intensity"           },
  { key: "ratio_oa_intensity",    apiName: "oa_intensity",      endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Other Asset Intensity"        },
  { key: "ratio_asset_intensity", apiName: "asset_intensity",   endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Total Asset Intensity"        },
  { key: "ratio_econ_eq_mult",    apiName: "econ_eq_mult",      endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Economic Equity Multiplier"   },
  { key: "ratio_revenue_growth",  apiName: "revenue_growth",    endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Revenue Growth"               },
  { key: "ratio_ee_growth",       apiName: "ee_growth",         endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Economic Equity Growth"       },
  { key: "ratio_ep_growth",       apiName: "ep_growth",         endpoint: "/api/v1/metrics/ratio-metrics", endpointType: "ratio_metrics", label: "Economic Profit Growth"       },

  // ── optimization_metrics — future endpoint ─────────────────────────────────
  { key: "intrinsic_wealth",   apiName: "Intrinsic Wealth",   endpoint: "/api/v1/metrics/optimization_metrics", endpointType: "get_metrics", label: "Intrinsic Wealth Creation"  },
  { key: "sustainable_wealth", apiName: "Sustainable Wealth", endpoint: "/api/v1/metrics/optimization_metrics", endpointType: "get_metrics", label: "Sustainable Wealth Creation" },

  // ── ep_series — Economic Profitability bow wave ─────────────────────────────
  // apiName is the temporal_window value, not a metric_name
  { key: "ep_1y",  apiName: "1Y",  endpoint: "/api/v1/metrics/economic-profitability", endpointType: "ep_series", label: "EP 1Y"  },
  { key: "ep_3y",  apiName: "3Y",  endpoint: "/api/v1/metrics/economic-profitability", endpointType: "ep_series", label: "EP 3Y"  },
  { key: "ep_5y",  apiName: "5Y",  endpoint: "/api/v1/metrics/economic-profitability", endpointType: "ep_series", label: "EP 5Y"  },
  { key: "ep_10y", apiName: "10Y", endpoint: "/api/v1/metrics/economic-profitability", endpointType: "ep_series", label: "EP 10Y" },
];

// ─── Convenience groupings (used by pages to avoid importing raw strings) ────

/** All get_metrics keys as their apiName strings — for useMultipleMetrics calls */
export const ALL_GET_METRIC_NAMES = METRIC_REGISTRY
  .filter(m => m.endpointType === "get_metrics")
  .map(m => m.apiName);

/** All ratio_metrics keys as their apiName strings — for MetricsDownloadPage */
export const ALL_RATIO_METRIC_NAMES = METRIC_REGISTRY
  .filter(m => m.endpointType === "ratio_metrics")
  .map(m => m.apiName);

/** Look up apiName by key — shorthand for pages that still call useMultipleMetrics */
export function apiName(key: string): string {
  return getMetricDef(key).apiName;
}
