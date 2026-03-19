/**
 * Principle 6 — Cost of Capital & Valuation
 * Live data: Calc Beta, Calc Rf, Calc KE via useMultipleMetrics (get_metrics)
 *            Calc 1Y FV ECF, Calc 3Y FV ECF, Calc 5Y FV ECF, Calc 10Y FV ECF
 * Sections: Beta Analysis | Ke Decomposition | Risk-Free Rate | FV-ECF / Valuation | TER Decomposition
 */
import { useState, useMemo } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine,
  ComposedChart, Area,
} from "recharts";
import { useActiveContext, useMultipleMetrics, useRatioMetric, groupByTicker } from "../hooks/useMetrics";

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
  { id: "6.1", label: "Beta Analysis" },
  { id: "6.2", label: "Ke Decomposition" },
  { id: "6.3", label: "Risk-Free Rate" },
  { id: "6.4", label: "FV-ECF / Valuation" },
  { id: "6.5", label: "TER Decomposition" },
];

const HELP: Record<string, string> = {
  "6.1": "Beta calculated via rolling 60-month OLS vs market index. 4-tier fallback: (1) company-specific (error < 0.8), (2) sector avg, (3) ticker historical avg, (4) market Beta 1.0. Final Beta = (slope × 2/3) + (1/3), rounded to 0.1.",
  "6.2": "Ke = Rf + Beta × MRP. Decomposition shows Rf component vs Beta×MRP. Falling Rf has driven secular Ke decline even with stable Beta — key driver of rising M:B ratios.",
  "6.3": "Rf is either FIXED (benchmark − risk_premium) or FLOATING (geometric mean of monthly government bond rates). AU 10Y bonds for AUS companies. Divergence creates different Ke environments.",
  "6.4": "FV-ECF = Σ(ECF_t × (1+Ke)^t) — compounding expected future ECF at Ke over 1Y, 3Y, 5Y, 10Y. Present value of future wealth delivery. Cornerstone of CISSA DCF valuation.",
  "6.5": "TER Decomposition: Open MC × Ke → add Dividends → add Capital Gains → add Franking → = TER. TER − Ke = excess return. TER Alpha = TER − Ke stripped of MRP = pure Alpha.",
};

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

// Build histogram buckets from a flat values array
function buildHistogram(values: number[], buckets = 12): { bucket: string; count: number }[] {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const step = (max - min) / buckets || 0.1;
  const hist = Array.from({ length: buckets }, (_, i) => ({
    bucket: `${(min + i * step).toFixed(2)}`,
    count: 0,
  }));
  values.forEach(v => {
    const idx = Math.min(buckets - 1, Math.floor((v - min) / step));
    hist[idx].count++;
  });
  return hist;
}

// Average of an array
function avg(arr: number[]): number {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}

export default function PrincipleSixPage() {
  const [activeTab, setActiveTab] = useState("6.1");

  const ctx = useActiveContext();
  const live = ctx.hasMetrics;
  const loading = ctx.loading;

  // Core metrics — Beta, Rf, Ke
  const coreMetrics = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, ["Calc Beta", "Calc Rf", "Calc KE"]);

  // FV-ECF metrics
  const fvEcfMetrics = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, [
    "Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF",
  ]);

  // TER and TER-Ke metrics for decomp
  const ter1Y = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio", "1Y");

  const allLoading = loading || coreMetrics.loading || fvEcfMetrics.loading;

  // ── Beta histogram ───────────────────────────────────────────────────────
  const betaHistogram = useMemo(() => {
    const betaItems = coreMetrics.data["Calc Beta"];
    if (!live || !betaItems?.length) {
      // Illustrative normal distribution around 0.9
      const vals = Array.from({ length: 60 }, () => 0.4 + Math.random() * 1.4);
      return buildHistogram(vals, 10);
    }
    const vals = betaItems.map(r => r.value).filter(v => v !== null && !isNaN(v as number)) as number[];
    return buildHistogram(vals, 10);
  }, [live, coreMetrics.data]);

  // ── Beta by ticker ─────────────────────────────────────────────────────
  const betaByTicker = useMemo(() => {
    const betaItems = coreMetrics.data["Calc Beta"];
    if (!live || !betaItems?.length) {
      return Array.from({ length: 12 }, (_, i) => ({ ticker: `T${i + 1}`, beta: 0.4 + Math.random() * 1.4 }));
    }
    const byT = groupByTicker(betaItems);
    return Object.entries(byT).slice(0, 14).map(([ticker, rows]) => {
      const vals = rows.map(r => r.value).filter(v => v !== null) as number[];
      return { ticker, beta: vals.length ? avg(vals) : 0 };
    }).sort((a, b) => b.beta - a.beta);
  }, [live, coreMetrics.data]);

  // ── Ke decomposition: Rf + Beta×MRP stacked by ticker ──────────────────
  const MRP: number = (ctx.params as any)?.mrp ?? 0.062; // Market risk premium from params
  const keDecomp = useMemo(() => {
    const keItems = coreMetrics.data["Calc KE"];
    const rfItems = coreMetrics.data["Calc Rf"];
    const betaItems = coreMetrics.data["Calc Beta"];
    if (!live || !keItems?.length) {
      return Array.from({ length: 12 }, (_, i) => {
        const rf = 0.025 + Math.random() * 0.02;
        const bxm = 0.04 + Math.random() * 0.06;
        return { ticker: `T${i + 1}`, rf: rf * 100, betaMrp: bxm * 100, ke: (rf + bxm) * 100 };
      });
    }
    const byTicker = groupByTicker(keItems);
    const rfByT = rfItems ? groupByTicker(rfItems) : {};
    const bByT = betaItems ? groupByTicker(betaItems) : {};
    return Object.entries(byTicker).slice(0, 14).map(([ticker, rows]) => {
      const keVal = avg(rows.map(r => r.value).filter(v => v !== null) as number[]);
      const rfRows = rfByT[ticker] ?? [];
      const rfVal = rfRows.length ? avg(rfRows.map(r => r.value).filter(v => v !== null) as number[]) : 0.03;
      const bRows = bByT[ticker] ?? [];
      const bVal = bRows.length ? avg(bRows.map(r => r.value).filter(v => v !== null) as number[]) : 1.0;
      return {
        ticker,
        rf: rfVal * 100,
        betaMrp: bVal * MRP * 100,
        ke: keVal * 100,
      };
    }).sort((a, b) => b.ke - a.ke);
  }, [live, coreMetrics.data, MRP]);

  // ── Rf time series ────────────────────────────────────────────────────────
  const rfTimeSeries = useMemo(() => {
    const rfItems = coreMetrics.data["Calc Rf"];
    if (!live || !rfItems?.length) {
      return ["2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024"].map(y => ({
        year: y,
        rf: (5 - (parseInt(y) - 2015) * 0.3 + Math.random() * 0.3),
      }));
    }
    // Group by year
    const byYear: Record<string, number[]> = {};
    rfItems.forEach(r => {
      const y = r.fiscal_year ? String(r.fiscal_year).slice(0, 4) : "?";
      if (!byYear[y]) byYear[y] = [];
      if (r.value !== null) byYear[y].push(r.value);
    });
    return Object.entries(byYear)
      .filter(([y]) => y !== "?")
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, vals]) => ({ year, rf: avg(vals) * 100 }));
  }, [live, coreMetrics.data]);

  // ── FV-ECF intervals: average per horizon ─────────────────────────────────
  const fvEcfBars = useMemo(() => {
    const horizons = [
      { key: "Calc 1Y FV ECF", label: "1Y FV-ECF" },
      { key: "Calc 3Y FV ECF", label: "3Y FV-ECF" },
      { key: "Calc 5Y FV ECF", label: "5Y FV-ECF" },
      { key: "Calc 10Y FV ECF", label: "10Y FV-ECF" },
    ];
    if (!live) {
      return horizons.map((h, i) => ({
        horizon: h.label,
        avgFvEcf: 120 + i * 85 + Math.random() * 30,
      }));
    }
    return horizons.map(h => {
      const items = fvEcfMetrics.data[h.key] ?? [];
      const vals = items.map(r => r.value).filter(v => v !== null) as number[];
      return {
        horizon: h.label,
        avgFvEcf: vals.length ? avg(vals) / 1e6 : 0, // in $M
      };
    });
  }, [live, fvEcfMetrics.data]);

  // ── FV-ECF by ticker (scatter 1Y vs 10Y) ─────────────────────────────────
  const fvEcfScatter = useMemo(() => {
    if (!live || !fvEcfMetrics.data["Calc 1Y FV ECF"]?.length) {
      return Array.from({ length: 20 }, (_, i) => ({
        ticker: `T${i + 1}`,
        fv1y: 10 + Math.random() * 300,
        fv10y: 30 + Math.random() * 800,
      }));
    }
    const fv1 = new Map((fvEcfMetrics.data["Calc 1Y FV ECF"] ?? []).map(r => [r.ticker, r.value]));
    const fv10 = new Map((fvEcfMetrics.data["Calc 10Y FV ECF"] ?? []).map(r => [r.ticker, r.value]));
    return [...fv1.keys()].slice(0, 20).map(t => ({
      ticker: t,
      fv1y: ((fv1.get(t) as number ?? 0) / 1e6),
      fv10y: ((fv10.get(t) as number ?? 0) / 1e6),
    }));
  }, [live, fvEcfMetrics.data]);

  // ── KPI tiles ─────────────────────────────────────────────────────────────
  const avgBeta = useMemo(() => {
    const items = coreMetrics.data["Calc Beta"];
    if (!items?.length) return null;
    const vals = items.map(r => r.value).filter(v => v !== null) as number[];
    return vals.length ? avg(vals).toFixed(2) : null;
  }, [coreMetrics.data]);

  const avgKe = useMemo(() => {
    const items = coreMetrics.data["Calc KE"];
    if (!items?.length) return null;
    const vals = items.map(r => r.value).filter(v => v !== null) as number[];
    return vals.length ? (avg(vals) * 100).toFixed(1) : null;
  }, [coreMetrics.data]);

  const avgRf = useMemo(() => {
    const items = coreMetrics.data["Calc Rf"];
    if (!items?.length) return null;
    const vals = items.map(r => r.value).filter(v => v !== null) as number[];
    return vals.length ? (avg(vals) * 100).toFixed(2) : null;
  }, [coreMetrics.data]);

  // TER Decomp waterfall (illustrative — real TER data from TER_ metrics)
  const terDecomp = [
    { name: "Open MC × Ke", value: 480, fill: NAV },
    { name: "+ Dividends", value: 85, fill: GREEN },
    { name: "+ Capital Gains", value: 120, fill: TEAL },
    { name: "+ Franking Credits", value: 28, fill: GOLD },
    { name: "= TER", value: 713, fill: PURPLE },
  ];

  return (
    <div style={{ padding: "28px 32px", background: LIGHT_BG, minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{ width: 4, height: 32, borderRadius: 2, background: GOLD }} />
          <h1 style={{ fontSize: 22, fontWeight: 800, color: NAV, margin: 0 }}>
            Principle 6 — Cost of Capital &amp; Valuation
          </h1>
          <Badge live={live} />
        </div>
        <p style={{ color: SLATE, fontSize: 14, margin: 0, paddingLeft: 16 }}>
          Beta analysis, Ke decomposition, risk-free rate history, FV-ECF valuation intervals, and TER attribution.
        </p>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 28 }}>
        {[
          { label: "Avg Beta", value: avgBeta ?? "—", unit: "" },
          { label: "Avg Ke", value: avgKe ? `${avgKe}%` : "—", unit: "" },
          { label: "Avg Rf", value: avgRf ? `${avgRf}%` : "—", unit: "" },
          { label: "MRP Assumption", value: `${(MRP * 100).toFixed(1)}%`, unit: "" },
        ].map(k => (
          <div key={k.label} style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: "16px 20px" }}>
            <div style={{ fontSize: 11, color: SLATE, fontWeight: 600, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 4 }}>{k.label}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: NAV }}>{k.value}{k.unit}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, background: "#e9eef5", padding: 4, borderRadius: 10, width: "fit-content" }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
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

      {/* ── 6.1 Beta Analysis ── */}
      {activeTab === "6.1" && (
        <>
          <Card title="Beta Distribution — Histogram" badge={live} help={HELP["6.1"]}>
            {allLoading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={betaHistogram} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: SLATE }}
                    label={{ value: "Beta", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: SLATE } }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} label={{ value: "Count", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: SLATE } }} />
                  <Tooltip formatter={(v: any) => [`${v}`, "Frequency"]} />
                  <ReferenceLine x="1.00" stroke={GOLD} strokeDasharray="4 4" />
                  <Bar dataKey="count" name="Frequency" radius={[4, 4, 0, 0]}>
                    {betaHistogram.map((entry, i) => (
                      <Cell key={i} fill={parseFloat(entry.bucket) >= 1 ? RED : NAV} opacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            <div style={{ display: "flex", gap: 20, marginTop: 12, fontSize: 12, color: SLATE }}>
              <span><span style={{ color: NAV, fontWeight: 700 }}>■</span> Beta &lt; 1 (Defensive)</span>
              <span><span style={{ color: RED, fontWeight: 700 }}>■</span> Beta ≥ 1 (Aggressive)</span>
              <span style={{ marginLeft: "auto" }}>Avg Beta: <strong style={{ color: NAV }}>{avgBeta ?? "—"}</strong></span>
            </div>
          </Card>

          <Card title="Beta by Company — Sorted" badge={live} help={HELP["6.1"]}>
            {allLoading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={betaByTicker} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis domain={[0, 2.2]} tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => v.toFixed(1)} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}`, "Beta"]} />
                  <ReferenceLine y={1} stroke={GOLD} strokeDasharray="4 4" label={{ value: "β=1.0", position: "insideTopRight", fill: GOLD, fontSize: 11 }} />
                  <Bar dataKey="beta" name="Calc Beta" radius={[4, 4, 0, 0]}>
                    {betaByTicker.map((r, i) => (
                      <Cell key={i} fill={r.beta >= 1 ? RED : NAV} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 6.2 Ke Decomposition ── */}
      {activeTab === "6.2" && (
        <>
          <Card title="Ke Decomposition — Rf + Beta×MRP by Company (%)" badge={live} help={HELP["6.2"]}>
            {allLoading ? <Skel h={300} /> : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={keDecomp} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="rf" name="Risk-Free Rate (Rf)" stackId="ke" fill={TEAL} />
                  <Bar dataKey="betaMrp" name="Beta × MRP" stackId="ke" fill={NAV} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Ke Distribution — Cross-Sectional" badge={live} help={HELP["6.2"]}>
            {allLoading ? <Skel h={240} /> : (() => {
              const keItems = coreMetrics.data["Calc KE"];
              const keBuckets = live && keItems?.length
                ? buildHistogram(keItems.map(r => r.value).filter(v => v !== null) as number[], 10).map(b => ({ ...b, bucket: `${(parseFloat(b.bucket) * 100).toFixed(1)}%` }))
                : buildHistogram(Array.from({ length: 50 }, () => 0.05 + Math.random() * 0.12), 10).map(b => ({ ...b, bucket: `${(parseFloat(b.bucket) * 100).toFixed(1)}%` }));
              return (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={keBuckets} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: SLATE }}
                      label={{ value: "Ke (%)", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: SLATE } }} />
                    <YAxis tick={{ fontSize: 11, fill: SLATE }} />
                    <Tooltip formatter={(v: any) => [`${v}`, "Count"]} />
                    <Bar dataKey="count" name="Frequency" fill={NAV} radius={[4, 4, 0, 0]} opacity={0.85} />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>
        </>
      )}

      {/* ── 6.3 Risk-Free Rate ── */}
      {activeTab === "6.3" && (
        <>
          <Card title="Risk-Free Rate History (%)" badge={live} help={HELP["6.3"]}>
            {allLoading ? <Skel h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={rfTimeSeries} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="year" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`, "Rf"]} />
                  <Area type="monotone" dataKey="rf" stroke={TEAL} fill={TEAL} fillOpacity={0.12} strokeWidth={2.5} name="Rf (%)" />
                  <Line type="monotone" dataKey="rf" stroke={TEAL} strokeWidth={2.5} dot={{ r: 4, fill: TEAL }} name="Rf" />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card title="Rf vs Ke Gap (Basis Points)" badge={live} help={HELP["6.3"]}>
            {allLoading ? <Skel h={240} /> : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  data={rfTimeSeries.map(r => ({
                    year: r.year,
                    rf: r.rf,
                    ke: r.rf + (MRP * 100 * (parseFloat(avgBeta ?? "1") || 1)),
                    gap: MRP * 100 * (parseFloat(avgBeta ?? "1") || 1),
                  }))}
                  margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="year" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="rf" stroke={TEAL} strokeWidth={2} dot={false} name="Rf" />
                  <Line type="monotone" dataKey="ke" stroke={NAV} strokeWidth={2} dot={false} name="Ke (avg)" />
                  <Line type="monotone" dataKey="gap" stroke={GOLD} strokeWidth={2} strokeDasharray="5 3" dot={false} name="Beta×MRP Gap" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 6.4 FV-ECF / Valuation ── */}
      {activeTab === "6.4" && (
        <>
          <Card title="FV-ECF by Horizon — Avg Portfolio ($M)" badge={live} help={HELP["6.4"]}>
            {allLoading ? <Skel h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={fvEcfBars} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="horizon" tick={{ fontSize: 12, fill: NAV, fontWeight: 600 }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `$${v.toFixed(0)}M`} />
                  <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(0)}M`, "Avg FV-ECF"]} />
                  <Bar dataKey="avgFvEcf" name="Avg FV-ECF ($M)" radius={[8, 8, 0, 0]}>
                    {fvEcfBars.map((_, i) => (
                      <Cell key={i} fill={[NAV, TEAL, GREEN, GOLD][i % 4]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            <div style={{ background: "#f8fafc", borderRadius: 8, padding: "12px 16px", fontSize: 13, color: SLATE, marginTop: 12, lineHeight: 1.7 }}>
              <strong style={{ color: NAV }}>Interpretation:</strong> FV-ECF compounds expected future ECF at Ke over each horizon. The 10Y FV-ECF represents the total discounted wealth a company is expected to deliver over a decade. High 10Y/1Y ratios indicate companies with long-duration compounding characteristics.
            </div>
          </Card>

          <Card title="FV-ECF 1Y vs 10Y by Company ($M)" badge={live} help={HELP["6.4"]}>
            {allLoading ? <Skel h={260} /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={fvEcfScatter.slice(0, 12)} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" />
                  <XAxis dataKey="ticker" tick={{ fontSize: 11, fill: SLATE }} />
                  <YAxis tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `$${v.toFixed(0)}M`} />
                  <Tooltip formatter={(v: any) => [`$${Number(v).toFixed(0)}M`]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="fv1y" name="1Y FV-ECF" fill={NAV} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="fv10y" name="10Y FV-ECF" fill={GOLD} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}

      {/* ── 6.5 TER Decomposition ── */}
      {activeTab === "6.5" && (
        <>
          <Card title="TER Decomposition Waterfall (Portfolio Avg, $M)" badge={false} help={HELP["6.5"]}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={terDecomp} layout="vertical" margin={{ top: 10, right: 60, left: 120, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: SLATE }} tickFormatter={v => `$${v}M`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: NAV, fontWeight: 600 }} width={120} />
                <Tooltip formatter={(v: any) => [`$${v}M`]} />
                <Bar dataKey="value" name="$M" radius={[0, 8, 8, 0]}>
                  {terDecomp.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ background: "#f8fafc", borderRadius: 8, padding: "12px 16px", fontSize: 13, color: SLATE, marginTop: 12, lineHeight: 1.7 }}>
              <strong style={{ color: NAV }}>Formula:</strong> TER = Open MC × Ke + Dividends + Capital Gains + Franking Credits. TER − Ke = Excess Return. TER Alpha = Excess Return − Beta×MRP = Pure Alpha (market-risk-adjusted).
            </div>
          </Card>

          <Card title="TER vs Ke — Alpha Attribution" badge={false} help={HELP["6.5"]}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {[
                { label: "Open MC × Ke", value: "$480M", pct: "67%", fill: NAV },
                { label: "Dividends", value: "$85M", pct: "12%", fill: GREEN },
                { label: "Capital Gains", value: "$120M", pct: "17%", fill: TEAL },
                { label: "Franking", value: "$28M", pct: "4%", fill: GOLD },
              ].map(c => (
                <div key={c.label} style={{ padding: "16px", background: "#f8fafc", borderRadius: 10, textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: c.fill, marginBottom: 2 }}>{c.value}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: SLATE }}>{c.pct}</div>
                  <div style={{ fontSize: 11, color: SLATE, marginTop: 4 }}>{c.label}</div>
                  <div style={{ height: 3, background: "#e2e8f0", borderRadius: 2, marginTop: 8 }}>
                    <div style={{ width: c.pct, height: "100%", background: c.fill, borderRadius: 2 }} />
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
