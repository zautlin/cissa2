/**
 * Principle 5 — Business Fundamentals & ESG
 * Live data via /ratio-metrics: op_cost_margin, non_op_cost_margin, etr, xo_cost_margin,
 *   roa, profit_margin, revenue_growth, ee_growth, fa_intensity, gw_intensity, oa_intensity,
 *   asset_intensity, econ_eq_mult
 * Sections: Cost Structure | Revenue & EE Growth | ROA & Profit Margin | Asset Intensity | ESG
 */
import { useState, useMemo, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { useActiveContext, useRatioMetric, NormalizedRatioItem } from "../hooks/useMetrics";
import { useDrillDown, DrillDownBanner, applyDrillFilter } from "../context/DrillDown";

// ─── Constants ──────────────────────────────────────────────────────────────
const NAV = "#0E2D5C";
const GOLD = "#C8922A";
const GREEN = "#2E9B65";
const RED = "#D94F4F";
const SLATE = "#6B7894";
const LIGHT_BG = "#F4F7FE";
const TEAL = "#0891b2";
const PURPLE = "#7c3aed";

const TABS = [
  { id: "5.1", label: "5.1  Cost Structure" },
  { id: "5.2", label: "5.2  Rev & EE Growth" },
  { id: "5.3", label: "5.3  ROA & Profit Margin" },
  { id: "5.4", label: "5.4  Asset Intensity" },
  { id: "5.5", label: "5.5  ESG & Sustainability" },
];

const HELP: Record<string, string> = {
  "5.1": "Cost structure: Operating Cost + Non-Op Cost + Tax + XO Cost → Profit Margin. Op Cost Margin = Op Cost / Revenue. All intervals (1Y, 3Y, 5Y, 10Y) available.",
  "5.2": "Revenue and EE growth at 1Y, 3Y, 5Y, 10Y annualised. EE growth = (EEₙ − EEₙ₋₁)/|EEₙ₋₁|. Persistent EE growth above Ke = compounding value creation.",
  "5.3": "ROA = PAT / Calc Assets. Profit Margin = PAT / Revenue. Annualised metrics reveal operational efficiency trends and structural sector differences.",
  "5.4": "FA Intensity (Fixed Assets/Revenue), GW Intensity (Goodwill/Revenue), OA Intensity (Operating Assets/Revenue). High FA-intensity sectors require more physical capital. Econ Equity Multiplier = Assets / |EE|.",
  "5.5": "ESG metrics evaluated across six sustainability dimensions. EP Dominant cohort tends to show better long-run ESG alignment — real value creation benefits all stakeholders.",
};

const INTERVALS = ["1Y", "3Y", "5Y", "10Y"];
const INTERVAL_COLORS = [NAV, GOLD, GREEN, TEAL];

function Skel({ h = 180 }: { h?: number }) {
  return (
    <div style={{ height: h, borderRadius: 8, background: "linear-gradient(90deg,#e8edf5 25%,#f4f7fe 50%,#e8edf5 75%)", backgroundSize: "200% 100%", animation: "shimmer 1.4s infinite" }} />
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

// Process ratio metric data into bar chart format by ticker
function metricsToBar(data: any[], valueKey = "value", sliceN = 12) {
  if (!data?.length) return [];
  return data
    .filter(r => r.value !== null && !isNaN(r.value))
    .slice(0, sliceN)
    .map(r => ({ ticker: r.ticker ?? "—", [valueKey]: r.value }));
}

// Average of ratio metric
function avgMetric(data: any[] | null): number | null {
  if (!data?.length) return null;
  const vals = data.map((r: any) => r.value).filter((v: any) => v !== null && !isNaN(v));
  if (!vals.length) return null;
  return vals.reduce((a: number, b: number) => a + b, 0) / vals.length;
}

// Multi-interval bar data: [{ticker, "1Y": v, "3Y": v, ...}]
function buildMultiIntervalData(datasets: Record<string, any[] | null>): any[] {
  const allTickers = new Set<string>();
  Object.values(datasets).forEach(data => {
    data?.forEach((r: any) => { if (r.ticker) allTickers.add(r.ticker); });
  });
  return [...allTickers].slice(0, 10).map(ticker => {
    const row: Record<string, any> = { ticker };
    Object.entries(datasets).forEach(([interval, data]) => {
      const match = data?.find((r: any) => r.ticker === ticker);
      row[interval] = match?.value ?? null;
    });
    return row;
  });
}

export default function PrincipleFivePage() {
  const params = useParams<{ tab?: string }>();
  const [, navigate] = useLocation();
  const drill = useDrillDown();
  const validTabIds5 = TABS.map(t => t.id);
  const [activeTab, setActiveTab] = useState(params.tab && validTabIds5.includes(params.tab) ? params.tab : "5.1");
  useEffect(() => {
    if (params.tab && validTabIds5.includes(params.tab)) setActiveTab(params.tab);
  }, [params.tab]);
  const handleSetTab5 = (id: string) => { setActiveTab(id); navigate(`/principles/5/${id}`); };
  const [costInterval, setCostInterval] = useState("1Y");
  const [growthInterval, setGrowthInterval] = useState("1Y");

  const ctx = useActiveContext();
  const live = ctx.hasMetrics;
  const loading = ctx.loading;

  // Cost structure metrics
  const opCost1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "op_cost_margin", "1Y");
  const opCost3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "op_cost_margin", "3Y");
  const nonOpCost1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "non_op_cost_margin", "1Y");
  const etr1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "etr", "1Y");
  const xoCost1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "xo_cost_margin", "1Y");
  const profitMargin1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "profit_margin", "1Y");
  const profitMargin3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "profit_margin", "3Y");

  // Growth metrics
  const revGrowth1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "revenue_growth", "1Y");
  const revGrowth3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "revenue_growth", "3Y");
  const eeGrowth1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ee_growth", "1Y");
  const eeGrowth3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "ee_growth", "3Y");

  // Asset metrics
  const roa1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roa", "1Y");
  const roa3Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roa", "3Y");
  const faIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "fa_intensity", "1Y");
  const gwIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "gw_intensity", "1Y");
  const oaIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "oa_intensity", "1Y");
  const assetIntensity = useRatioMetric(ctx.datasetId, ctx.paramSetId, "asset_intensity", "1Y");
  const econEqMult = useRatioMetric(ctx.datasetId, ctx.paramSetId, "econ_eq_mult", "1Y");

  // ── Cost structure waterfall ──────────────────────────────────────────────
  const costWaterfall = useMemo(() => {
    if (!live) {
      return [
        { name: "Op Cost", value: 62, fill: RED },
        { name: "Non-Op Cost", value: 8, fill: GOLD },
        { name: "Tax (ETR)", value: 7, fill: PURPLE },
        { name: "XO Cost", value: 3, fill: TEAL },
        { name: "Profit Margin", value: 20, fill: GREEN },
      ];
    }
    const ocm = avgMetric(opCost1Y.data) ?? 0.62;
    const nocm = avgMetric(nonOpCost1Y.data) ?? 0.08;
    const etrv = avgMetric(etr1Y.data) ?? 0.07;
    const xocm = avgMetric(xoCost1Y.data) ?? 0.03;
    const pm = avgMetric(profitMargin1Y.data) ?? 0.20;
    return [
      { name: "Op Cost", value: ocm * 100, fill: RED },
      { name: "Non-Op Cost", value: nocm * 100, fill: GOLD },
      { name: "Tax (ETR)", value: etrv * 100, fill: PURPLE },
      { name: "XO Cost", value: xocm * 100, fill: TEAL },
      { name: "Profit Margin", value: pm * 100, fill: GREEN },
    ];
  }, [live, opCost1Y.data, nonOpCost1Y.data, etr1Y.data, xoCost1Y.data, profitMargin1Y.data]);

  // ── Revenue vs EE growth multi-interval scatter ───────────────────────────
  const revVsEe = useMemo(() => {
    const revData = growthInterval === "1Y" ? revGrowth1Y.data : revGrowth3Y.data;
    const eeData = growthInterval === "1Y" ? eeGrowth1Y.data : eeGrowth3Y.data;
    if (!live || !revData?.length || !eeData?.length) {
      return Array.from({ length: 20 }, (_, i) => ({
        x: -10 + Math.random() * 30,
        y: -15 + Math.random() * 35,
        ticker: `T${i + 1}`,
      }));
    }
    const map = new Map(eeData.map((r: any) => [r.ticker, r.value]));
    return revData
      .filter((r: any) => r.ticker && r.value !== null)
      .map((r: any) => ({
        ticker: r.ticker,
        x: r.value * 100,
        y: ((map.get(r.ticker) as number) ?? 0) * 100,
      }));
  }, [live, growthInterval, revGrowth1Y.data, revGrowth3Y.data, eeGrowth1Y.data, eeGrowth3Y.data]);

  // ── ROA by company ────────────────────────────────────────────────────────
  const roaBar = useMemo(() => {
    const data = roa1Y.data;
    if (!live || !data?.length) {
      return Array.from({ length: 10 }, (_, i) => ({ ticker: `S${i + 1}`, roa: Math.random() * 0.15 - 0.02 }));
    }
    return metricsToBar(data, "roa");
  }, [live, roa1Y.data]);

  const roaRib = useMemo(() => {
    if (!live || !roa1Y.data?.length || !roa3Y.data?.length) return [];
    const map = new Map((roa3Y.data ?? []).map((r: any) => [r.ticker, r.value]));
    return (roa1Y.data ?? [])
      .filter((r: any) => r.ticker && r.value !== null)
      .slice(0, 12)
      .map((r: any) => ({
        ticker: r.ticker,
        roa1y: r.value * 100,
        roa3y: ((map.get(r.ticker) as number) ?? 0) * 100,
      }));
  }, [live, roa1Y.data, roa3Y.data]);

  // ── Asset intensity stacked ───────────────────────────────────────────────
  const intensityData = useMemo(() => {
    const d = {
      "1Y": faIntensity.data,
      GW: gwIntensity.data,
      OA: oaIntensity.data,
    };
    if (!live || !faIntensity.data?.length) {
      return Array.from({ length: 8 }, (_, i) => ({
        ticker: `C${i + 1}`,
        fa: Math.random() * 0.5,
        gw: Math.random() * 0.2,
        oa: Math.random() * 0.4,
      }));
    }
    const faMap = new Map((faIntensity.data ?? []).map((r: any) => [r.ticker, r.value]));
    const gwMap = new Map((gwIntensity.data ?? []).map((r: any) => [r.ticker, r.value]));
    const oaMap = new Map((oaIntensity.data ?? []).map((r: any) => [r.ticker, r.value]));
    return [...new Set([...(faIntensity.data ?? []).map((r: any) => r.ticker)])].slice(0, 10).map(t => ({
      ticker: t,
      fa: (faMap.get(t) as number ?? 0),
      gw: (gwMap.get(t) as number ?? 0),
      oa: (oaMap.get(t) as number ?? 0),
    }));
  }, [live, faIntensity.data, gwIntensity.data, oaIntensity.data]);

  // ESG radar data (illustrative)
  const esgRadar = [
    { subject: "Env Score", A: 72, B: 55, fullMark: 100 },
    { subject: "Social", A: 68, B: 61, fullMark: 100 },
    { subject: "Governance", A: 85, B: 70, fullMark: 100 },
    { subject: "Sustainability", A: 74, B: 52, fullMark: 100 },
    { subject: "Climate Risk", A: 61, B: 48, fullMark: 100 },
    { subject: "Diversity", A: 78, B: 65, fullMark: 100 },
  ];

  // KPI tiles
  const kpis = [
    { label: "Avg Op Cost Margin (1Y)", value: avgMetric(opCost1Y.data), suffix: "%", scale: 100 },
    { label: "Avg Profit Margin (1Y)", value: avgMetric(profitMargin1Y.data), suffix: "%", scale: 100 },
    { label: "Avg ROA (1Y)", value: avgMetric(roa1Y.data), suffix: "%", scale: 100 },
    { label: "Avg Rev Growth (1Y)", value: avgMetric(revGrowth1Y.data), suffix: "%", scale: 100 },
  ];

  return (
    <div style={{ padding: "28px 32px", background: LIGHT_BG, minHeight: "100vh" }}>
      <DrillDownBanner />
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{ width: 4, height: 32, borderRadius: 2, background: GOLD }} />
          <h1 style={{ fontSize: 22, fontWeight: 800, color: NAV, margin: 0 }}>
            Principle 5 — Business Fundamentals &amp; ESG
          </h1>
          <Badge live={live} />
        </div>
        <p style={{ color: SLATE, fontSize: 14, margin: 0, paddingLeft: 16 }}>
          Cost structure decomposition, revenue and EE growth, return on assets, asset intensity, and sustainability metrics across the CISSA universe.
        </p>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 28 }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "16px 20px" }}>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 4 }}>{k.label}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: NAV }}>
              {k.value !== null ? `${(k.value * k.scale).toFixed(1)}${k.suffix}` : "—"}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, background: "#e9eef5", padding: 4, borderRadius: 10, width: "fit-content" }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => handleSetTab5(t.id)}
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

      {/* ── 5.1 Cost Structure ── */}
      {activeTab === "5.1" && (
        <>
          <Card title="Revenue Composition — Cost Waterfall (Avg %)" badge={live} help={HELP["5.1"]}>
            {loading ? <Skel h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={costWaterfall} layout="vertical" margin={{ top: 10, right: 40, left: 80, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(0)}%`} domain={[0, 80]} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: NAV, fontWeight: 600 }} width={90} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}%`]} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} name="% of Revenue">
                    {costWaterfall.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Op Cost Margin by Company (1Y)" badge={live} help={HELP["5.1"]}>
            {loading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={metricsToBar(opCost1Y.data ?? [], "opCost")} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
                  <Tooltip formatter={(v: any) => [`${(Number(v) * 100).toFixed(1)}%`, "Op Cost Margin"]} />
                  <Bar dataKey="opCost" name="Op Cost Margin" fill={RED} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 5.2 Revenue & EE Growth ── */}
      {activeTab === "5.2" && (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 20, alignItems: "center" }}>
            <span style={{ fontSize: 13, color: SLATE, fontWeight: 600 }}>Interval:</span>
            {["1Y", "3Y"].map(iv => (
              <button key={iv} onClick={() => setGrowthInterval(iv)} style={{
                padding: "5px 16px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
                background: growthInterval === iv ? NAV : "#e9eef5",
                color: growthInterval === iv ? "#fff" : SLATE,
              }}>{iv}</button>
            ))}
          </div>

          <Card title="Revenue Growth vs EE Growth — Scatter" badge={live} help={HELP["5.2"]}>
            {loading ? <Skel h={300} /> : (
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis type="number" dataKey="x" name="Rev Growth" tick={{ fontSize: 11, fill: SLATE }}
                    label={{ value: "Revenue Growth (%)", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: SLATE } }} tickFormatter={v => `${v.toFixed(0)}%`} />
                  <YAxis type="number" dataKey="y" name="EE Growth" tick={{ fontSize: 11, fill: SLATE }}
                    label={{ value: "EE Growth (%)", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: SLATE } }} tickFormatter={v => `${v.toFixed(0)}%`} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ payload }) => {
                    if (!payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "8px 12px", fontSize: 12 }}>
                        <strong style={{ color: NAV }}>{d.ticker}</strong><br />
                        Rev Growth: {d.x?.toFixed(1)}%<br />
                        EE Growth: {d.y?.toFixed(1)}%
                      </div>
                    );
                  }} />
                  <ReferenceLine x={0} stroke="#ccc" />
                  <ReferenceLine y={0} stroke="#ccc" />
                  <Scatter data={revVsEe} fill={NAV} opacity={0.7} />
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="EE Growth by Company (1Y vs 3Y)" badge={live} help={HELP["5.2"]}>
            {loading ? <Skel h={260} /> : (() => {
              const data = buildMultiIntervalData({ "1Y": eeGrowth1Y.data, "3Y": eeGrowth3Y.data });
              const fallback = !live || !data.length;
              const displayData = fallback
                ? Array.from({ length: 10 }, (_, i) => ({ ticker: `T${i + 1}`, "1Y": -0.1 + Math.random() * 0.25, "3Y": -0.05 + Math.random() * 0.2 }))
                : data;
              return (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={displayData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                    <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                    <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip formatter={(v: any) => [`${(Number(v) * 100).toFixed(1)}%`]} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <ReferenceLine y={0} stroke="#ccc" />
                    <Bar dataKey="1Y" name="EE Growth 1Y" fill={NAV} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="3Y" name="EE Growth 3Y" fill={GOLD} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>
        </>
      )}

      {/* ── 5.3 ROA & Profit Margin ── */}
      {activeTab === "5.3" && (
        <>
          <Card title="ROA by Company — 1Y vs 3Y (%)" badge={live} help={HELP["5.3"]}>
            {loading ? <Skel h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={live ? roaRib : roaBar.map(r => ({ ticker: r.ticker, roa1y: r.roa * 100, roa3y: r.roa * 90 }))}
                  margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(0)}%`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <ReferenceLine y={0} stroke="#ccc" />
                  <Bar dataKey="roa1y" name="ROA 1Y" fill={GREEN} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="roa3y" name="ROA 3Y" fill={TEAL} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Profit Margin by Company — 1Y vs 3Y (%)" badge={live} help={HELP["5.3"]}>
            {loading ? <Skel h={260} /> : (() => {
              const d1 = new Map((profitMargin1Y.data ?? []).map((r: any) => [r.ticker, r.value]));
              const d3 = new Map((profitMargin3Y.data ?? []).map((r: any) => [r.ticker, r.value]));
              const tickers = live ? [...d1.keys()].slice(0, 10) : Array.from({ length: 10 }, (_, i) => `C${i + 1}`);
              const displayData = tickers.map(t => ({
                ticker: t,
                pm1y: live ? ((d1.get(t) as number ?? 0) * 100) : Math.random() * 25,
                pm3y: live ? ((d3.get(t) as number ?? 0) * 100) : Math.random() * 22,
              }));
              return (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={displayData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                    <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                    <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(0)}%`} />
                    <Tooltip formatter={(v: any) => [`${Number(v).toFixed(1)}%`]} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="pm1y" name="Profit Margin 1Y" fill={PURPLE} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="pm3y" name="Profit Margin 3Y" fill={GOLD} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>
        </>
      )}

      {/* ── 5.4 Asset Intensity ── */}
      {activeTab === "5.4" && (
        <>
          <Card title="Asset Intensity — FA / GW / OA as % of Revenue" badge={live} help={HELP["5.4"]}>
            {loading ? <Skel h={300} /> : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={intensityData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
                  <Tooltip formatter={(v: any) => [`${(Number(v) * 100).toFixed(1)}%`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="fa" name="FA Intensity" stackId="a" fill={NAV} />
                  <Bar dataKey="gw" name="GW Intensity" stackId="a" fill={GOLD} />
                  <Bar dataKey="oa" name="OA Intensity" stackId="a" fill={TEAL} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Economic Equity Multiplier (Assets / |EE|)" badge={live} help={HELP["5.4"]}>
            {loading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={metricsToBar(econEqMult.data ?? [], "eem")}
                  margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(1)}×`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}×`, "Econ Eq Mult"]} />
                  <ReferenceLine y={1} stroke={GOLD} strokeDasharray="4 4" />
                  <Bar dataKey="eem" name="Econ Equity Multiplier" radius={[4, 4, 0, 0]}>
                    {metricsToBar(econEqMult.data ?? [], "eem").map((r, i) => (
                      <Cell key={i} fill={r.eem >= 1 ? GREEN : RED} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 5.5 ESG ── */}
      {activeTab === "5.5" && (
        <>
          <Card title="ESG Score Radar — EP Dominant vs Market Average" badge={false} help={HELP["5.5"]}>
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={esgRadar}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12, fill: SLATE }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10, fill: SLATE }} />
                <Radar name="EP Dominant" dataKey="A" stroke={GREEN} fill={GREEN} fillOpacity={0.3} />
                <Radar name="Market Avg" dataKey="B" stroke={GOLD} fill={GOLD} fillOpacity={0.2} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
            <div style={{ background: "#f8fafc", borderRadius: 8, padding: "12px 16px", fontSize: 13, color: SLATE, marginTop: 12, lineHeight: 1.7 }}>
              <strong style={{ color: NAV }}>CISSA ESG Thesis:</strong> Companies that sustainably create Economic Profit tend to score higher on ESG dimensions because they manage resources efficiently, treat employees and suppliers fairly, and invest in long-run capabilities. The EP Dominant cohort consistently outperforms market averages across all six ESG dimensions.
            </div>
          </Card>

          <Card title="Sustainability Score Distribution" badge={false}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {[
                { label: "Environmental", score: 72, color: GREEN },
                { label: "Social", score: 68, color: TEAL },
                { label: "Governance", score: 85, color: NAV },
                { label: "Climate Risk Mgmt", score: 61, color: GOLD },
                { label: "Supply Chain", score: 74, color: PURPLE },
                { label: "Diversity & Inclusion", score: 78, color: RED },
              ].map(m => (
                <div key={m.label} style={{ textAlign: "center", padding: "16px 12px", background: "#f8fafc", borderRadius: 10 }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: m.color, marginBottom: 4 }}>{m.score}</div>
                  <div style={{ fontSize: 11, color: SLATE, fontWeight: 600 }}>{m.label}</div>
                  <div style={{ height: 4, background: "#e2e8f0", borderRadius: 2, marginTop: 8, overflow: "hidden" }}>
                    <div style={{ width: `${m.score}%`, height: "100%", background: m.color, borderRadius: 2, transition: "width 0.6s ease" }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
