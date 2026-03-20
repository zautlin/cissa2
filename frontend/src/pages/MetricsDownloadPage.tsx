/**
 * MetricsDownloadPage — Live CSV/JSON export of all computed metrics
 * Fetches live data from getMetrics() + getRatioMetrics() then exports
 */
import { useState, useMemo, useCallback } from "react";
import { useActiveContext, useMultipleMetrics, useRatioMetric } from "../hooks/useMetrics";

const NAV = "#0E2D5C";
const GOLD = "#C8922A";
const GREEN = "#2E9B65";
const SLATE = "#6B7894";
const RED = "#D94F4F";
const LIGHT_BG = "#F4F7FE";
const TEAL = "#0891b2";
const PURPLE = "#7c3aed";

// All metric names we can export
const ALL_METRICS = [
  // L1
  "Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost", "Calc Non Op Cost",
  "Calc Tax Cost", "Calc XO Cost", "Calc ECF", "Non Div ECF", "Calc EE",
  "Calc FY TSR", "Calc FY TSR PREL",
  // Runtime
  "Calc Beta", "Calc Rf", "Calc Ke",
  // L2 Core
  "Calc EP", "Calc PAT_Ex", "Calc XO_Cost_Ex", "Calc FC",
  // FV-ECF
  "Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF",
  // TER
  "Calc 1Y TER", "Calc 3Y TER", "Calc 5Y TER", "Calc 10Y TER",
  "Calc 1Y TER-KE", "Calc 3Y TER-KE", "Calc 5Y TER-KE", "Calc 10Y TER-KE",
  // TER Alpha
  "Calc 1Y TER Alpha", "Calc 3Y TER Alpha", "Calc 5Y TER Alpha", "Calc 10Y TER Alpha",
];

const RATIO_METRICS = [
  "mb_ratio", "roee", "roa", "profit_margin", "op_cost_margin",
  "non_op_cost_margin", "etr", "xo_cost_margin", "fa_intensity",
  "gw_intensity", "oa_intensity", "asset_intensity", "econ_eq_mult",
  "revenue_growth", "ee_growth", "ep_growth",
];

const INTERVALS = ["1Y", "3Y", "5Y", "10Y"];

type ExportFormat = "csv" | "json";
type ExportCategory = "core" | "fv_ecf" | "ter" | "ter_alpha" | "ratio" | "all";

interface ExportConfig {
  category: ExportCategory;
  format: ExportFormat;
  interval: string;
}

function Skel({ h = 40 }: { h?: number }) {
  return (
    <div style={{ height: h, borderRadius: 8, background: "linear-gradient(90deg,#e8edf5 25%,#f4f7fe 50%,#e8edf5 75%)", backgroundSize: "200% 100%", animation: "shimmer 1.4s infinite", marginBottom: 8 }} />
  );
}

function Badge({ live }: { live: boolean }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: 1, padding: "2px 8px", borderRadius: 20,
      background: live ? "#e6f9ef" : "#fff8e6", color: live ? GREEN : GOLD,
      border: `1px solid ${live ? "#b3e8cc" : "#f5d99a"}`,
    }}>
      {live ? "● LIVE" : "ILLUS."}
    </span>
  );
}

// Convert flat metric items to CSV string
function toCsv(rows: any[]): string {
  if (!rows.length) return "no data\n";
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map(r => headers.map(h => {
      const v = r[h];
      if (v === null || v === undefined) return "";
      if (typeof v === "string" && v.includes(",")) return `"${v}"`;
      return String(v);
    }).join(","))
  ];
  return lines.join("\n");
}

function downloadText(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function MetricsDownloadPage() {
  const ctx = useActiveContext();
  const live = ctx.hasMetrics;
  const loading = ctx.loading;

  const [selectedCategory, setSelectedCategory] = useState<ExportCategory>("all");
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("csv");
  const [selectedInterval, setSelectedInterval] = useState("1Y");
  const [isExporting, setIsExporting] = useState(false);
  const [lastExport, setLastExport] = useState<{ filename: string; rows: number } | null>(null);

  // Fetch all core metrics
  const coreData = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, ALL_METRICS);

  // Fetch ratio metrics for selected interval
  const mbRatio = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio", selectedInterval);
  const roee = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roee", selectedInterval);
  const roa = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roa", selectedInterval);
  const profitMargin = useRatioMetric(ctx.datasetId, ctx.paramSetId, "profit_margin", selectedInterval);
  const opCostMargin = useRatioMetric(ctx.datasetId, ctx.paramSetId, "op_cost_margin", selectedInterval);
  const nonOpCostMargin = useRatioMetric(ctx.datasetId, ctx.paramSetId, "non_op_cost_margin", selectedInterval);
  const etr = useRatioMetric(ctx.datasetId, ctx.paramSetId, "etr", selectedInterval);
  const revGrowth = useRatioMetric(ctx.datasetId, ctx.paramSetId, "revenue_growth", selectedInterval);
  const eeGrowth = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ee_growth", selectedInterval);
  const epGrowth = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ep_growth", selectedInterval);
  const faIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "fa_intensity", selectedInterval);
  const gwIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "gw_intensity", selectedInterval);
  const oaIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "oa_intensity", selectedInterval);
  const assetIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "asset_intensity", selectedInterval);
  const econEqMult = useRatioMetric(ctx.datasetId, ctx.paramSetId, "econ_eq_mult", selectedInterval);
  const xoCostMargin = useRatioMetric(ctx.datasetId, ctx.paramSetId, "xo_cost_margin", selectedInterval);

  const ratioDataMap: Record<string, any[]> = useMemo(() => ({
    mb_ratio: mbRatio.data ?? [],
    roee: roee.data ?? [],
    roa: roa.data ?? [],
    profit_margin: profitMargin.data ?? [],
    op_cost_margin: opCostMargin.data ?? [],
    non_op_cost_margin: nonOpCostMargin.data ?? [],
    etr: etr.data ?? [],
    revenue_growth: revGrowth.data ?? [],
    ee_growth: eeGrowth.data ?? [],
    ep_growth: epGrowth.data ?? [],
    fa_intensity: faIntensity.data ?? [],
    gw_intensity: gwIntensity.data ?? [],
    oa_intensity: oaIntensity.data ?? [],
    asset_intensity: assetIntensity.data ?? [],
    econ_eq_mult: econEqMult.data ?? [],
    xo_cost_margin: xoCostMargin.data ?? [],
  }), [mbRatio.data, roee.data, roa.data, profitMargin.data, opCostMargin.data,
      nonOpCostMargin.data, etr.data, revGrowth.data, eeGrowth.data, epGrowth.data,
      faIntensity.data, gwIntensity.data, oaIntensity.data, assetIntensity.data,
      econEqMult.data, xoCostMargin.data]);

  // ── Stats summary ─────────────────────────────────────────────────────────
  const totalCoreRows = useMemo(() => {
    return Object.values(coreData.data).reduce((sum, arr) => sum + (arr?.length ?? 0), 0);
  }, [coreData.data]);

  const totalRatioRows = useMemo(() => {
    return Object.values(ratioDataMap).reduce((sum, arr) => sum + arr.length, 0);
  }, [ratioDataMap]);

  // ── Export handler ────────────────────────────────────────────────────────
  const handleExport = useCallback(() => {
    if (!live) {
      alert("No live data available. Please run the ETL pipeline first.");
      return;
    }
    setIsExporting(true);

    try {
      let exportRows: any[] = [];
      let filename = `cissa_metrics_${ctx.datasetId ?? "data"}`;

      if (selectedCategory === "ratio" || selectedCategory === "all") {
        // Pivot ratio metrics into wide format: one row per ticker
        const allTickers = new Set<string>();
        Object.values(ratioDataMap).forEach(arr => arr.forEach((r: any) => { if (r.ticker) allTickers.add(r.ticker); }));

        const pivoted = [...allTickers].map(ticker => {
          const row: Record<string, any> = { ticker, dataset_id: ctx.datasetId, param_set_id: ctx.paramSetId, interval: selectedInterval };
          RATIO_METRICS.forEach(m => {
            const arr = ratioDataMap[m] ?? [];
            const match = arr.find((r: any) => r.ticker === ticker);
            row[m] = match?.value ?? null;
          });
          return row;
        });

        if (selectedCategory === "ratio") {
          exportRows = pivoted;
          filename += `_ratio_${selectedInterval}`;
        } else {
          exportRows = pivoted;
        }
      }

      if (selectedCategory !== "ratio") {
        const metricsToExport = selectedCategory === "all"
          ? ALL_METRICS
          : selectedCategory === "core" ? ["Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost", "Calc Non Op Cost", "Calc Tax Cost", "Calc XO Cost", "Calc ECF", "Non Div ECF", "Calc EE", "Calc FY TSR", "Calc Beta", "Calc Rf", "Calc Ke", "Calc EP", "Calc PAT_Ex", "Calc XO_Cost_Ex", "Calc FC"]
          : selectedCategory === "fv_ecf" ? ["Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF"]
          : selectedCategory === "ter" ? ["Calc 1Y TER", "Calc 3Y TER", "Calc 5Y TER", "Calc 10Y TER", "Calc 1Y TER-KE", "Calc 3Y TER-KE", "Calc 5Y TER-KE", "Calc 10Y TER-KE"]
          : ["Calc 1Y TER Alpha", "Calc 3Y TER Alpha", "Calc 5Y TER Alpha", "Calc 10Y TER Alpha"];

        const metricRows: any[] = [];
        metricsToExport.forEach(metric => {
          const items = coreData.data[metric] ?? [];
          items.forEach(item => {
            metricRows.push({
              metric_name: metric,
              ticker: item.ticker ?? null,
              year_ending: item.fiscal_year ?? null,
              value: item.value,
              dataset_id: ctx.datasetId,
              param_set_id: ctx.paramSetId,
            });
          });
        });

        if (selectedCategory === "all") {
          // Merge ratio rows and metric rows
          const allRatio = exportRows.map(r => ({ type: "ratio", ...r }));
          exportRows = [...metricRows.map(r => ({ type: "metric", ...r })), ...allRatio];
        } else {
          exportRows = metricRows;
          filename += `_${selectedCategory}`;
        }
      }

      filename += `_${new Date().toISOString().slice(0, 10)}`;

      let totalRows = exportRows.length;

      if (selectedFormat === "json") {
        downloadText(JSON.stringify(exportRows, null, 2), `${filename}.json`, "application/json");
      } else {
        downloadText(toCsv(exportRows), `${filename}.csv`, "text/csv");
      }

      setLastExport({ filename: `${filename}.${selectedFormat}`, rows: totalRows });
    } finally {
      setIsExporting(false);
    }
  }, [live, selectedCategory, selectedFormat, selectedInterval, coreData.data, ratioDataMap, ctx]);

  // Category descriptions
  const CATEGORIES: { id: ExportCategory; label: string; count: number; desc: string }[] = [
    { id: "all", label: "All Metrics", count: totalCoreRows + totalRatioRows, desc: "Every computed metric in one export" },
    { id: "core", label: "Core L1 + Runtime", count: totalCoreRows, desc: "L1 metrics, Beta, Rf, Ke, EP core" },
    { id: "fv_ecf", label: "FV-ECF Valuation", count: (coreData.data["Calc 1Y FV ECF"]?.length ?? 0) * 4, desc: "Future value ECF at 1Y/3Y/5Y/10Y horizons" },
    { id: "ter", label: "TER & TER-Ke", count: (coreData.data["Calc 1Y TER"]?.length ?? 0) * 8, desc: "Total equity return and excess over Ke" },
    { id: "ter_alpha", label: "TER Alpha", count: (coreData.data["Calc 1Y TER Alpha"]?.length ?? 0) * 4, desc: "Risk-adjusted alpha at all intervals" },
    { id: "ratio", label: "Ratio Metrics", count: totalRatioRows, desc: "All 16 ratio metrics for chosen interval" },
  ];

  return (
    <div style={{ padding: "28px 32px", background: LIGHT_BG, minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{ width: 4, height: 32, borderRadius: 2, background: GOLD }} />
          <h1 style={{ fontSize: 22, fontWeight: 800, color: NAV, margin: 0 }}>Metrics Export</h1>
          <Badge live={live} />
        </div>
        <p style={{ color: SLATE, fontSize: 14, margin: 0, paddingLeft: 16 }}>
          Download all computed CISSA metrics as CSV or JSON. Data is fetched live from the API.
          {ctx.datasetId && <span style={{ color: NAV, fontWeight: 600 }}> Dataset: {ctx.datasetId}</span>}
        </p>
      </div>

      {/* Dataset info */}
      {loading ? (
        <div style={{ marginBottom: 20 }}><Skel h={80} /></div>
      ) : (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "20px 24px", marginBottom: 28, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Dataset ID</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: NAV, marginTop: 2 }}>{ctx.datasetId ?? "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Param Set</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: NAV, marginTop: 2 }}>{ctx.paramSetId ?? "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Core Metric Rows</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: live ? GREEN : SLATE, marginTop: 2 }}>{live ? totalCoreRows.toLocaleString() : "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Ratio Metric Rows</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: live ? GREEN : SLATE, marginTop: 2 }}>{live ? totalRatioRows.toLocaleString() : "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Metrics Available</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: NAV, marginTop: 2 }}>{ALL_METRICS.length + RATIO_METRICS.length} metrics</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Status</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: live ? GREEN : GOLD, marginTop: 2 }}>{live ? "● Ready" : "○ Awaiting pipeline"}</div>
          </div>
        </div>
      )}

      {/* Export config */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24, marginBottom: 28 }}>
        {/* Step 1: Category */}
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "20px 24px" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: GOLD, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 14 }}>
            Step 1 — Select Metrics
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {CATEGORIES.map(cat => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                style={{
                  padding: "10px 14px", borderRadius: 8, border: `1.5px solid ${selectedCategory === cat.id ? NAV : "#e2e8f0"}`,
                  background: selectedCategory === cat.id ? `${NAV}12` : "#fafbfd",
                  cursor: "pointer", textAlign: "left", transition: "all 0.12s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 700, fontSize: 13, color: selectedCategory === cat.id ? NAV : "#334" }}>{cat.label}</span>
                  {live && cat.count > 0 && (
                    <span style={{ fontSize: 10, color: GREEN, fontWeight: 700, background: "#e6f9ef", padding: "1px 6px", borderRadius: 10 }}>
                      {cat.count.toLocaleString()} rows
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: SLATE, marginTop: 2 }}>{cat.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Options */}
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "20px 24px" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: GOLD, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 14 }}>
            Step 2 — Options
          </div>

          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, color: SLATE, fontWeight: 600, marginBottom: 8 }}>Format</div>
            <div style={{ display: "flex", gap: 8 }}>
              {(["csv", "json"] as ExportFormat[]).map(fmt => (
                <button key={fmt} onClick={() => setSelectedFormat(fmt)} style={{
                  flex: 1, padding: "10px 0", borderRadius: 8, border: `1.5px solid ${selectedFormat === fmt ? NAV : "#e2e8f0"}`,
                  background: selectedFormat === fmt ? NAV : "#fafbfd",
                  color: selectedFormat === fmt ? "#fff" : SLATE,
                  cursor: "pointer", fontWeight: 700, fontSize: 13, textTransform: "uppercase",
                }}>
                  .{fmt}
                </button>
              ))}
            </div>
          </div>

          {(selectedCategory === "ratio" || selectedCategory === "all") && (
            <div>
              <div style={{ fontSize: 12, color: SLATE, fontWeight: 600, marginBottom: 8 }}>Ratio Interval</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
                {INTERVALS.map(iv => (
                  <button key={iv} onClick={() => setSelectedInterval(iv)} style={{
                    padding: "8px 0", borderRadius: 8, border: `1.5px solid ${selectedInterval === iv ? GOLD : "#e2e8f0"}`,
                    background: selectedInterval === iv ? GOLD : "#fafbfd",
                    color: selectedInterval === iv ? "#fff" : SLATE,
                    cursor: "pointer", fontWeight: 700, fontSize: 12,
                  }}>
                    {iv}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: 20, padding: "12px 14px", background: "#f8fafc", borderRadius: 8, fontSize: 12, color: SLATE, lineHeight: 1.6 }}>
            <strong style={{ color: NAV }}>Export includes:</strong><br />
            Ticker, Year Ending, Metric Value, Dataset ID, Param Set ID
          </div>
        </div>

        {/* Step 3: Export */}
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "20px 24px", display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: GOLD, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 14 }}>
            Step 3 — Download
          </div>

          <div style={{ flex: 1, padding: "16px", background: "#f8fafc", borderRadius: 10, marginBottom: 20 }}>
            <div style={{ fontSize: 13, color: NAV, fontWeight: 700, marginBottom: 8 }}>Export Summary</div>
            <div style={{ fontSize: 13, color: SLATE, lineHeight: 2 }}>
              <span style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Category:</span> <strong style={{ color: NAV }}>{CATEGORIES.find(c => c.id === selectedCategory)?.label}</strong>
              </span>
              <span style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Format:</span> <strong style={{ color: NAV }}>.{selectedFormat}</strong>
              </span>
              {(selectedCategory === "ratio" || selectedCategory === "all") && (
                <span style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Interval:</span> <strong style={{ color: NAV }}>{selectedInterval}</strong>
                </span>
              )}
              <span style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Dataset:</span> <strong style={{ color: NAV }}>{ctx.datasetId ?? "—"}</strong>
              </span>
              <span style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Data status:</span> <strong style={{ color: live ? GREEN : GOLD }}>{live ? "Live" : "No data"}</strong>
              </span>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={!live || isExporting || coreData.loading}
            style={{
              padding: "14px 0", borderRadius: 10, border: "none", cursor: live ? "pointer" : "not-allowed",
              background: live ? NAV : "#c5ccd8", color: "#fff",
              fontWeight: 800, fontSize: 15, letterSpacing: 0.5,
              opacity: isExporting ? 0.7 : 1,
              transition: "all 0.15s",
            }}
          >
            {isExporting ? "Exporting..." : `⬇ Download .${selectedFormat.toUpperCase()}`}
          </button>

          {!live && (
            <div style={{ marginTop: 12, fontSize: 12, color: GOLD, textAlign: "center", fontWeight: 600 }}>
              Run ETL pipeline to enable export
            </div>
          )}

          {lastExport && (
            <div style={{ marginTop: 12, padding: "10px 14px", background: "#e6f9ef", borderRadius: 8, fontSize: 12, color: GREEN }}>
              ✓ Exported <strong>{lastExport.filename}</strong> ({lastExport.rows.toLocaleString()} rows)
            </div>
          )}
        </div>
      </div>

      {/* Metric reference table */}
      <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "20px 24px" }}>
        <div style={{ fontWeight: 700, fontSize: 15, color: NAV, marginBottom: 16 }}>Available Metrics Reference</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
          {[
            { group: "L1 Computed", metrics: ["Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost", "Calc Non Op Cost", "Calc Tax Cost", "Calc XO Cost", "Calc ECF", "Non Div ECF", "Calc EE", "Calc FY TSR", "Calc FY TSR PREL"], color: NAV },
            { group: "Runtime (Beta/Ke/Rf)", metrics: ["Calc Beta", "Calc Rf", "Calc Ke"], color: TEAL },
            { group: "L2 Core EP", metrics: ["Calc EP", "Calc PAT_Ex", "Calc XO_Cost_Ex", "Calc FC"], color: GREEN },
            { group: "FV-ECF Valuation", metrics: ["Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF"], color: GOLD },
            { group: "TER / TER-Ke / Alpha", metrics: ["Calc 1Y TER", "Calc 3Y TER", "Calc 5Y TER", "Calc 10Y TER", "Calc 1Y TER-KE", "Calc 1Y TER Alpha", "Calc 3Y TER Alpha"], color: PURPLE },
            { group: "Ratio Metrics (16 total)", metrics: ["mb_ratio", "roee", "roa", "profit_margin", "op_cost_margin", "etr", "revenue_growth", "ee_growth", "ep_growth", "fa_intensity", "asset_intensity", "econ_eq_mult"], color: RED },
          ].map(group => (
            <div key={group.group} style={{ padding: "14px", background: "#f8fafc", borderRadius: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: group.color, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
                {group.group}
              </div>
              {group.metrics.map(m => (
                <div key={m} style={{ fontSize: 12, color: SLATE, padding: "2px 0", borderBottom: "1px dashed #ebebeb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontFamily: "monospace", fontSize: 11 }}>{m}</span>
                  {live && coreData.data[m]?.length ? (
                    <span style={{ fontSize: 10, color: GREEN, fontWeight: 700 }}>{coreData.data[m].length}</span>
                  ) : null}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


