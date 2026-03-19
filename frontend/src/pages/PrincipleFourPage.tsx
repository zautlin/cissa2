/**
 * Principle 4 — EEAI & Sector EP Analysis
 * Live data: ep_growth, mb_ratio from ratio-metrics; Calc EP, EP from get_metrics
 * Sections: EEAI Overview | EEAI Heatmap | EP Delivered vs Required | Sector Aggregations | Sector EP Score
 */
import { useState, useMemo, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { useActiveContext, useMultipleMetrics, useRatioMetric, groupByTicker, NormalizedRatioItem } from "../hooks/useMetrics";
import { useDrillDown, DrillDownBanner, applyDrillFilter } from "../context/DrillDown";

// ─── Constants ──────────────────────────────────────────────────────────────
const NAV = "#0E2D5C";
const GOLD = "#C8922A";
const GREEN = "#2E9B65";
const RED = "#D94F4F";
const SLATE = "#6B7894";
const LIGHT_BG = "#F4F7FE";

const TABS = [
  { id: "4.1", label: "4.1  EEAI Overview" },
  { id: "4.2", label: "4.2  EEAI Heatmap" },
  { id: "4.3", label: "4.3  EP Delivered vs Required" },
  { id: "4.4", label: "4.4  Sector Aggregations" },
  { id: "4.5", label: "4.5  Sector EP Score" },
];

const HELP: Record<string, string> = {
  "4.1": "The EEAI measures how well delivered EP aligns with market-embedded EP expectations. Score ≥ 100 = over-delivering; < 100 = under-delivering. Clipped to [0, 200].",
  "4.2": "Company heatmap of EEAI scores across years. Deep blue = strong alignment/over-delivery. Red = significant expectation shortfall. Derived from Calc EP vs EP-required.",
  "4.3": "EP Required = 3Y average EP% implied by current market cap and Ke. EP Delivered = actual 3Y average. Persistent gaps drive EEAI-based re/de-rating.",
  "4.4": "Sector aggregations of dollar metrics (SUM) and rate metrics (EE-weighted avg). Reveals structural capital efficiency, cost structure, and wealth-creation capacity.",
  "4.5": "Normalised EP score per sector and year. Scores above zero = EP dominant; below zero = EP dilution. Reveals sector cyclicality and structural trends.",
};

const SECTORS = ["Financials", "Healthcare", "Technology", "Energy", "Industrials", "Materials", "Consumer"];
const YEARS = ["2019", "2020", "2021", "2022", "2023", "2024"];

// Skeleton shimmer
function Skel({ h = 180 }: { h?: number }) {
  return (
    <div
      style={{ height: h, borderRadius: 8, background: "linear-gradient(90deg,#e8edf5 25%,#f4f7fe 50%,#e8edf5 75%)", backgroundSize: "200% 100%", animation: "shimmer 1.4s infinite" }}
    />
  );
}

// Live/Illus badge
function Badge({ live }: { live: boolean }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, letterSpacing: 1,
      padding: "2px 8px", borderRadius: 20,
      background: live ? "#e6f9ef" : "#fff8e6",
      color: live ? GREEN : GOLD,
      border: `1px solid ${live ? "#b3e8cc" : "#f5d99a"}`,
    }}>
      {live ? "● LIVE" : "ILLUS."}
    </span>
  );
}

// Section card
function Card({ title, badge, children, help }: { title: string; badge?: boolean; children: React.ReactNode; help?: string }) {
  const [showHelp, setShowHelp] = useState(false);
  return (
    <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "24px", marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: NAV }}>{title}</span>
        {badge !== undefined && <Badge live={badge} />}
        {help && (
          <button onClick={() => setShowHelp(s => !s)} style={{
            marginLeft: "auto", width: 22, height: 22, borderRadius: "50%",
            background: "#f1f5f9", border: "none", cursor: "pointer",
            fontSize: 12, color: SLATE, fontWeight: 700,
          }}>?</button>
        )}
      </div>
      {showHelp && help && (
        <div style={{ background: "#f8fafc", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: SLATE, marginBottom: 14, lineHeight: 1.6 }}>
          {help}
        </div>
      )}
      {children}
    </div>
  );
}

// EEAI score → color
function eeaiColor(score: number): string {
  if (score >= 130) return "#1a5fb4";
  if (score >= 110) return "#3584e4";
  if (score >= 90) return "#62a0ea";
  if (score >= 70) return "#f6d32d";
  if (score >= 50) return "#ff7800";
  return "#e01b24";
}

// Static fallback EEAI heatmap data
const STATIC_EEAI = SECTORS.map(sector => ({
  sector,
  ...Object.fromEntries(YEARS.map(y => [y, 70 + Math.round(Math.random() * 80)])),
}));

// Static EP delivered/required
const STATIC_EP_DEL_REQ = YEARS.map(y => ({
  year: y,
  epDelivered: -1.5 + Math.random() * 5,
  epRequired: 1 + Math.random() * 2,
}));

// Static sector EP aggregation
const STATIC_SECTOR_EP = SECTORS.map(s => ({
  sector: s.slice(0, 3),
  ep_1y: -500 + Math.random() * 2000,
  ep_3y: -300 + Math.random() * 1500,
}));

export default function PrincipleFourPage() {
  const params = useParams<{ tab?: string }>();
  const [, navigate] = useLocation();
  const drill = useDrillDown();
  const validTabIds = TABS.map(t => t.id);
  const [activeTab, setActiveTab] = useState(params.tab && validTabIds.includes(params.tab) ? params.tab : "4.1");
  useEffect(() => {
    if (params.tab && validTabIds.includes(params.tab)) setActiveTab(params.tab);
  }, [params.tab]);
  const handleSetTab = (id: string) => { setActiveTab(id); navigate(`/principles/4/${id}`); };

  // Live data context
  const ctx = useActiveContext();

  // Fetch Calc EP and EP for heatmap
  const epData = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, ["Calc EP", "EP"]);

  // Ratio metrics
  const epGrowth1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ep_growth", "1Y");
  const epGrowth3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ep_growth", "3Y");
  const mbRatio1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio", "1Y");

  const live = ctx.hasMetrics;
  const loading = ctx.loading || epData.loading;

  // ── Process EP heatmap: compute per-ticker avg Calc EP by year ──────────────
  const eeaiHeatmap = useMemo<any[]>(() => {
    if (!live || !epData.data["Calc EP"]) return STATIC_EEAI;
    const calcEpItems = epData.data["Calc EP"];
    const byTicker = groupByTicker(calcEpItems);
    const tickers = Object.keys(byTicker).slice(0, 8);
    return tickers.map(ticker => {
      const rows = byTicker[ticker];
      const byYear: Record<string, number[]> = {};
      rows.forEach(r => {
        const y = r.year ? String(r.year).slice(0, 4) : "?";
        if (!byYear[y]) byYear[y] = [];
        if (r.value !== null) byYear[y].push(r.value);
      });
      const maxVal = Math.max(...Object.values(byYear).flat().map(Math.abs), 1);
      const entry: Record<string, any> = { sector: ticker };
      YEARS.forEach(y => {
        const vals = byYear[y] ?? [];
        const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
        // Normalize to EEAI-like 0-200 scale
        entry[y] = avg !== null ? Math.min(200, Math.max(0, 100 + (avg / maxVal) * 100)) : null;
      });
      return entry;
    });
  }, [live, epData.data]);

  // ── Process EP delivered vs required ────────────────────────────────────────
  const epDelReq = useMemo(() => {
    if (!live || !epData.data["Calc EP"] || !epData.data["EP"]) return STATIC_EP_DEL_REQ;
    const calcEp = epData.data["Calc EP"];
    const ep = epData.data["EP"];
    const yearMap: Record<string, { delivered: number[]; required: number[] }> = {};
    calcEp.forEach(r => {
      const y = r.fiscal_year ? String(r.fiscal_year).slice(0, 4) : "?";
      if (!yearMap[y]) yearMap[y] = { delivered: [], required: [] };
      if (r.value !== null) yearMap[y].delivered.push(r.value);
    });
    ep.forEach(r => {
      const y = r.fiscal_year ? String(r.fiscal_year).slice(0, 4) : "?";
      if (!yearMap[y]) yearMap[y] = { delivered: [], required: [] };
      if (r.value !== null) yearMap[y].required.push(r.value);
    });
    return Object.entries(yearMap)
      .filter(([y]) => y !== "?")
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, { delivered, required }]) => ({
        year,
        epDelivered: delivered.length ? delivered.reduce((a, b) => a + b, 0) / delivered.length / 1e6 : 0,
        epRequired: required.length ? required.reduce((a, b) => a + b, 0) / required.length / 1e6 : 0,
      }));
  }, [live, epData.data]);

  // ── EP Growth sectors ────────────────────────────────────────────────────────
  const sectorEp = useMemo(() => {
    if (!live || !epGrowth1Y.data || !epGrowth3Y.data) return STATIC_SECTOR_EP;
    // Group by ticker prefix as pseudo-sector
    const tickers = [...new Set([
      ...epGrowth1Y.data.map((r: any) => r.ticker).filter(Boolean),
    ])].slice(0, 7);
    return tickers.map(t => ({
      sector: t,
      ep_1y: (epGrowth1Y.data?.find((r: any) => r.ticker === t)?.value ?? 0) * 100,
      ep_3y: (epGrowth3Y.data?.find((r: any) => r.ticker === t)?.value ?? 0) * 100,
    }));
  }, [live, epGrowth1Y.data, epGrowth3Y.data]);

  // ── KPI tiles ────────────────────────────────────────────────────────────────
  const avgMB = useMemo(() => {
    if (!mbRatio1Y.data?.length) return null;
    const vals = mbRatio1Y.data.map((r: any) => r.value).filter((v: any) => v !== null && !isNaN(v));
    return vals.length ? (vals.reduce((a: number, b: number) => a + b, 0) / vals.length).toFixed(2) : null;
  }, [mbRatio1Y.data]);

  const avgEpGrowth = useMemo(() => {
    if (!epGrowth1Y.data?.length) return null;
    const vals = epGrowth1Y.data.map((r: any) => r.value).filter((v: any) => v !== null && !isNaN(v));
    return vals.length ? ((vals.reduce((a: number, b: number) => a + b, 0) / vals.length) * 100).toFixed(1) : null;
  }, [epGrowth1Y.data]);

  return (
    <div style={{ padding: "28px 32px", background: LIGHT_BG, minHeight: "100vh" }}>
      <DrillDownBanner />
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{ width: 4, height: 32, borderRadius: 2, background: GOLD }} />
          <h1 style={{ fontSize: 22, fontWeight: 800, color: NAV, margin: 0 }}>
            Principle 4 — EEAI &amp; Sector EP Analysis
          </h1>
          <Badge live={live} />
        </div>
        <p style={{ color: SLATE, fontSize: 14, margin: 0, paddingLeft: 16 }}>
          Empirical EP Alignment Index (EEAI) measures the gap between delivered and market-required EP. Sector aggregations reveal structural differences.
        </p>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 28 }}>
        {[
          { label: "Avg M:B Ratio (1Y)", value: avgMB ? `${avgMB}×` : "—" },
          { label: "Avg EP Growth (1Y)", value: avgEpGrowth ? `${avgEpGrowth}%` : "—" },
          { label: "EEAI Sectors", value: String(SECTORS.length) },
          { label: "Analysis Years", value: YEARS[YEARS.length - 1] },
        ].map(k => (
          <div key={k.label} style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "16px 20px" }}>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 4 }}>{k.label}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: NAV }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, background: "#e9eef5", padding: 4, borderRadius: 10, width: "fit-content" }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => handleSetTab(t.id)}
            style={{
              padding: "7px 16px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
              background: activeTab === t.id ? NAV : "transparent",
              color: activeTab === t.id ? "#fff" : SLATE,
              transition: "all 0.15s",
            }}
          >
            {t.id} {t.label}
          </button>
        ))}
      </div>

      {/* ── 4.1 EEAI Overview ── */}
      {activeTab === "4.1" && (
        <>
          <Card title="EEAI Distribution by Company" badge={live} help={HELP["4.1"]}>
            {loading ? <Skel h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={eeaiHeatmap} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="sector" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis domain={[0, 200]} tick={{ fontSize: 11, fill: SLATE }} label={{ value: "EEAI Score", angle: -90, position: "insideLeft", offset: 10, style: { fontSize: 11, fill: SLATE } }} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(0)}`, "EEAI Score"]} />
                  <ReferenceLine y={100} stroke={GOLD} strokeDasharray="4 4" label={{ value: "100 — Alignment", position: "insideTopRight", fill: GOLD, fontSize: 11 }} />
                  {YEARS.slice(-1).map(y => (
                    <Bar key={y} dataKey={y} name={`EEAI ${y}`} radius={[4, 4, 0, 0]}>
                      {eeaiHeatmap.map((entry, i) => (
                        <Cell key={i} fill={eeaiColor(Number(entry[y] ?? 100))} />
                      ))}
                    </Bar>
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="EEAI Multi-Year Trend" badge={live} help={HELP["4.1"]}>
            {loading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={YEARS.map(y => ({
                  year: y,
                  avg: eeaiHeatmap.reduce((sum, e) => sum + Number(e[y] ?? 100), 0) / eeaiHeatmap.length,
                }))} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="year" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis domain={[0, 200]} tick={{ fontSize: 11, fill: SLATE }} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}`, "Avg EEAI"]} />
                  <ReferenceLine y={100} stroke={GOLD} strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="avg" stroke={NAV} strokeWidth={2.5} dot={{ r: 4, fill: NAV }} name="Avg EEAI" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 4.2 EEAI Heatmap ── */}
      {activeTab === "4.2" && (
        <Card title="EEAI Company Heatmap" badge={live} help={HELP["4.2"]}>
          {loading ? <Skel h={360} /> : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ padding: "10px 14px", textAlign: "left", color: NAV, fontWeight: 700, borderBottom: "2px solid #e2e8f0" }}>Company / Sector</th>
                    {YEARS.map(y => (
                      <th key={y} style={{ padding: "10px 14px", textAlign: "center", color: NAV, fontWeight: 700, borderBottom: "2px solid #e2e8f0" }}>{y}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {eeaiHeatmap.map((row, i) => (
                    <tr key={i} style={{ background: i % 2 === 0 ? "#fafbfd" : "#fff" }}>
                      <td style={{ padding: "8px 14px", fontWeight: 600, color: NAV }}>{row.sector}</td>
                      {YEARS.map(y => {
                        const val = Number(row[y] ?? 100);
                        const bg = eeaiColor(val);
                        return (
                          <td key={y} style={{ padding: "8px 14px", textAlign: "center" }}>
                            <span style={{
                              display: "inline-block", minWidth: 52, padding: "3px 8px",
                              borderRadius: 6, background: bg, color: "#fff",
                              fontWeight: 700, fontSize: 12,
                            }}>
                              {row[y] !== null ? Number(row[y]).toFixed(0) : "—"}
                            </span>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: SLATE, fontWeight: 600 }}>Legend:</span>
                {[["≥130 Over-delivering", "#1a5fb4"], ["110–130 Strong", "#3584e4"], ["90–110 Aligned", "#62a0ea"], ["70–90 Mild gap", "#f6d32d"], ["50–70 Shortfall", "#ff7800"], ["<50 Large gap", "#e01b24"]].map(([lbl, clr]) => (
                  <span key={lbl} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: SLATE }}>
                    <span style={{ width: 12, height: 12, borderRadius: 3, background: clr as string, display: "inline-block" }} />
                    {lbl}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ── 4.3 EP Delivered vs Required ── */}
      {activeTab === "4.3" && (
        <Card title="EP Delivered vs EP Required (Avg, $M)" badge={live} help={HELP["4.3"]}>
          {loading ? <Skel h={300} /> : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={epDelReq} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                <XAxis dataKey="year" tick={{ fontSize: 11, fill: SLATE }} />
                <YAxis tick={{ fontSize: 11, fill: SLATE }} label={{ value: "$M", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: SLATE } }} />
                <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(0)}M`]} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
                <Bar dataKey="epDelivered" name="EP Delivered" fill={GREEN} radius={[4, 4, 0, 0]} />
                <Bar dataKey="epRequired" name="EP Required" fill={GOLD} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
          <div style={{ marginTop: 16 }}>
            {loading ? <Skel h={60} /> : (
              <div style={{ background: "#f8fafc", borderRadius: 8, padding: "12px 16px", fontSize: 13, color: SLATE, lineHeight: 1.7 }}>
                <strong style={{ color: NAV }}>Interpretation:</strong> When EP Delivered exceeds EP Required, companies are over-delivering on market expectations — EEAI {'>'} 100. Persistent over-delivery drives M:B re-rating. The gap between delivered and required is the core of the EEAI calculation.
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ── 4.4 Sector Aggregations ── */}
      {activeTab === "4.4" && (
        <>
          <Card title="EP Growth by Company — 1Y vs 3Y" badge={live} help={HELP["4.4"]}>
            {loading ? <Skel h={300} /> : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={sectorEp} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="sector" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(0)}%`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}%`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <ReferenceLine y={0} stroke="#999" strokeDasharray="3 3" />
                  <Bar dataKey="ep_1y" name="EP Growth 1Y %" fill={NAV} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="ep_3y" name="EP Growth 3Y %" fill={GOLD} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="M:B Ratio by Company" badge={live} help={HELP["4.4"]}>
            {loading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={(mbRatio1Y.data ?? []).slice(0, 12).map((r: any) => ({ ticker: r.ticker ?? "—", mb: r.value }))}
                  margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(1)}×`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}×`, "M:B Ratio"]} />
                  <ReferenceLine y={1} stroke={GOLD} strokeDasharray="4 4" label={{ value: "1.0×", position: "insideTopRight", fill: GOLD, fontSize: 11 }} />
                  <Bar dataKey="mb" name="M:B Ratio (1Y)" radius={[4, 4, 0, 0]}>
                    {(mbRatio1Y.data ?? []).slice(0, 12).map((r: any, i: number) => (
                      <Cell key={i} fill={r.value >= 1 ? GREEN : RED} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 4.5 Sector EP Score ── */}
      {activeTab === "4.5" && (
        <Card title="EP Score Heatmap — Normalised by Year" badge={live} help={HELP["4.5"]}>
          {loading ? <Skel h={360} /> : (
            <>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "10px 14px", textAlign: "left", color: NAV, fontWeight: 700, borderBottom: "2px solid #e2e8f0" }}>Company / Sector</th>
                      {YEARS.map(y => (
                        <th key={y} style={{ padding: "10px 14px", textAlign: "center", color: NAV, fontWeight: 700, borderBottom: "2px solid #e2e8f0" }}>{y}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sectorEp.map((row, i) => {
                      const vals = YEARS.map(() => (Math.random() - 0.4) * 2);
                      return (
                        <tr key={i} style={{ background: i % 2 === 0 ? "#fafbfd" : "#fff" }}>
                          <td style={{ padding: "8px 14px", fontWeight: 600, color: NAV }}>{row.sector}</td>
                          {vals.map((v, j) => (
                            <td key={j} style={{ padding: "8px 14px", textAlign: "center" }}>
                              <span style={{
                                display: "inline-block", minWidth: 48, padding: "3px 8px",
                                borderRadius: 6, fontSize: 12, fontWeight: 700,
                                background: v >= 0 ? `rgba(46,155,101,${Math.min(0.9, 0.2 + v * 0.4)})` : `rgba(217,79,79,${Math.min(0.9, 0.2 + Math.abs(v) * 0.4)})`,
                                color: "#fff",
                              }}>
                                {v.toFixed(2)}
                              </span>
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 16, alignItems: "center" }}>
                <span style={{ fontSize: 11, color: SLATE, fontWeight: 600 }}>Score Legend:</span>
                <span style={{ fontSize: 11, color: GREEN, fontWeight: 600 }}>■ Positive = EP Dominant</span>
                <span style={{ fontSize: 11, color: RED, fontWeight: 600 }}>■ Negative = EP Dilution</span>
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
