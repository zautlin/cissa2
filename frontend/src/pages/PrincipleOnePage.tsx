/**
 * Principle 1 — Economic Measures are Better
 * Live data: Ke, Beta, Rf, ratio metrics (mb_ratio, roee, roa, profit_margin)
 * Tabs: 1.1 Ke | 1.2 Financial Bridge | 1.3 Products & Services | 1.4 Predictor | 1.5 Assessment
 */
import { useState, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import {
  ComposedChart, BarChart, ScatterChart,
  Area, Bar, Line, Scatter, XAxis, YAxis, ZAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import {
  useActiveContext, useMultipleMetrics, useRatioMetric,
  aggregateByYear, NormalizedRatioItem,
} from "../hooks/useMetrics";
import { useDrillDown, DrillDownBanner, applyDrillFilter } from "../context/DrillDown";

const NAVY = "hsl(213 75% 22%)";
const GOLD = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)";
const SLATE = "hsl(215 15% 46%)";
const CHART_COLORS = [NAVY, GOLD, GREEN, "hsl(280 55% 50%)", "hsl(0 60% 50%)", "hsl(188 70% 40%)"];

const TAB_IDS = ["1.1", "1.2", "1.3", "1.4", "1.5"];
const TAB_LABELS = [
  "1.1  Cost of Equity (Ke)",
  "1.2  Financial & Capital Bridge",
  "1.3  Products & Services",
  "1.4  Capital Market Predictor",
  "1.5  Capital Market Assessment",
];

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: "0.35rem 0.75rem",
      background: active ? NAVY : "transparent",
      color: active ? "#fff" : SLATE,
      border: `1px solid ${active ? NAVY : "hsl(210 16% 88%)"}`,
      borderRadius: 6, fontSize: "0.6875rem", fontWeight: active ? 700 : 500,
      cursor: "pointer", transition: "all 0.15s",
    }}>{label}</button>
  );
}

function ChartCard({ title, subtitle, live, children }: {
  title: string; subtitle?: string; live?: boolean; children: React.ReactNode;
}) {
  return (
    <div style={{ background: "#fff", borderRadius: 10, border: "1px solid hsl(210 16% 90%)", padding: "1rem 1.25rem", boxShadow: "0 1px 4px hsl(213 40% 50% / 0.05)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.875rem" }}>
        <div>
          <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 12%)" }}>{title}</div>
          {subtitle && <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.125rem" }}>{subtitle}</div>}
        </div>
        {live !== undefined && (
          <span style={{
            fontSize: "0.5625rem", fontWeight: 700, padding: "0.15rem 0.45rem",
            background: live ? "hsl(152 60% 40% / 0.1)" : "hsl(38 60% 52% / 0.1)",
            color: live ? "hsl(152 50% 30%)" : "hsl(38 60% 35%)",
            borderRadius: 999, border: live ? "1px solid hsl(152 60% 40% / 0.3)" : "1px solid hsl(38 60% 52% / 0.3)",
            textTransform: "uppercase",
          }}>
            {live ? "● LIVE" : "ILLUS."}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function Skeleton({ h = 200 }: { h?: number }) {
  return <div style={{ height: h, background: "hsl(210 20% 95%)", borderRadius: 8, animation: "shimmer 1.4s infinite", backgroundImage: "linear-gradient(90deg,hsl(210 20% 95%),hsl(210 20% 92%),hsl(210 20% 95%))", backgroundSize: "200% 100%" }} />;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#fff", border: "1px solid hsl(210 16% 88%)", borderRadius: 8, padding: "0.5rem 0.75rem", boxShadow: "0 4px 16px rgba(0,0,0,0.10)", fontSize: "0.75rem" }}>
      <div style={{ fontWeight: 700, color: "hsl(220 35% 18%)", marginBottom: "0.25rem" }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color, display: "flex", gap: "0.5rem" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, marginTop: 3 }} />
          <span>{p.name}: <b>{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</b></span>
        </div>
      ))}
    </div>
  );
};

export default function PrincipleOnePage() {
  const params = useParams<{ tab?: string }>();
  const [, navigate] = useLocation();
  const drill = useDrillDown();

  // Sync tab index from URL param
  const tabFromUrl = params.tab ? TAB_IDS.indexOf(params.tab) : -1;
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0);
  useEffect(() => {
    const idx = params.tab ? TAB_IDS.indexOf(params.tab) : -1;
    if (idx >= 0) setTab(idx);
  }, [params.tab]);

  const handleTabClick = (i: number) => {
    setTab(i);
    navigate(`/principles/1/${TAB_IDS[i]}`);
  };

  const ctx = useActiveContext();
  const multiMetrics = useMultipleMetrics(
    ctx.datasetId, ctx.paramSetId,
    ["Calc Beta", "Calc KE", "Calc Rf", "Calc ECF", "Calc FY TSR"]
  );
  const mbRatio   = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio",      "1Y");
  const roee      = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roee",          "1Y");
  const roa       = useRatioMetric(ctx.datasetId, ctx.paramSetId, "roa",           "3Y");
  const profitMgn = useRatioMetric(ctx.datasetId, ctx.paramSetId, "profit_margin", "3Y");
  const opCost    = useRatioMetric(ctx.datasetId, ctx.paramSetId, "op_cost_margin","1Y");
  const etr       = useRatioMetric(ctx.datasetId, ctx.paramSetId, "etr",           "1Y");

  const loading = ctx.loading || multiMetrics.loading;

  const keAgg   = aggregateByYear(multiMetrics.data["Calc KE"]    || []);
  const rfAgg   = aggregateByYear(multiMetrics.data["Calc Rf"]    || []);
  const betaAgg = aggregateByYear(multiMetrics.data["Calc Beta"]  || []);
  const tsrAgg  = aggregateByYear(multiMetrics.data["Calc FY TSR"]|| []);

  // Build Ke decomposition chart
  const keDecompData = keAgg.map(ke => {
    const rf   = rfAgg.find(r => r.year === ke.year)?.value ?? (ctx.params?.fixed_benchmark_return_wealth_preservation as number ?? 7.5) / 100;
    const beta = betaAgg.find(b => b.year === ke.year)?.value ?? 1.0;
    const erp  = (ctx.params?.equity_risk_premium as number ?? 5.0) / 100;
    return {
      year: String(ke.year),
      rf:    +(rf * 100).toFixed(2),
      erp:   +(beta * erp * 100).toFixed(2),
      ke:    +(ke.value * 100).toFixed(2),
    };
  }).filter(d => d.year >= "2005");

  // MB ratio using normalized NormalizedRatioItem[]
  const mbRatioFiltered: NormalizedRatioItem[] = applyDrillFilter(mbRatio.data || [], drill);
  const mbByYear = mbRatioFiltered.length > 0 ? (() => {
    const m: Record<string, number[]> = {};
    mbRatioFiltered.forEach((r) => {
      (r.time_series || []).forEach((ts) => {
        if (ts.value !== null) {
          const y = String(ts.year);
          if (!m[y]) m[y] = [];
          m[y].push(ts.value);
        }
      });
    });
    return Object.entries(m).map(([year, vals]) => ({
      year,
      median: +(vals.sort((a, b) => a - b)[Math.floor(vals.length / 2)]).toFixed(2),
    })).sort((a, b) => a.year.localeCompare(b.year)).slice(-15);
  })() : null;

  // ROEE data using normalized type
  const roeeFiltered: NormalizedRatioItem[] = applyDrillFilter(roee.data || [], drill);

  // Op cost sector data
  const opCostFiltered: NormalizedRatioItem[] = applyDrillFilter(opCost.data || [], drill);

  // ETR data
  const etrFiltered: NormalizedRatioItem[] = applyDrillFilter(etr.data || [], drill);

  // Fallback static data
  const keDecompFallback = [
    { year: "2010", rf: 5.1, erp: 5.0, ke: 10.1 },
    { year: "2012", rf: 4.2, erp: 5.0, ke: 9.2  },
    { year: "2014", rf: 3.5, erp: 5.3, ke: 8.8  },
    { year: "2016", rf: 2.8, erp: 5.2, ke: 8.0  },
    { year: "2018", rf: 2.1, erp: 5.5, ke: 7.6  },
    { year: "2020", rf: 0.8, erp: 5.8, ke: 6.6  },
    { year: "2022", rf: 2.8, erp: 5.3, ke: 8.1  },
    { year: "2024", rf: 4.2, erp: 5.0, ke: 9.2  },
  ];

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1600 }}>
      {/* DrillDown Banner */}
      <DrillDownBanner />

      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
          Principle 1 — Economic Measures are Better
        </h1>
        <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0" }}>
          Cost of Equity Capital · Financial Bridge · CAPM · Ke Decomposition
        </p>
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
        {TAB_LABELS.map((t, i) => <Chip key={i} label={t} active={tab === i} onClick={() => handleTabClick(i)} />)}
      </div>

      {/* Tab 1.1: Ke Decomposition */}
      {tab === 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1rem" }}>
          <ChartCard title="Ke Decomposition: Rf + Beta × ERP" subtitle="CAPM breakdown by component over time (%)" live={keDecompData.length > 0}>
            {loading ? <Skeleton /> : (
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={keDecompData.length > 0 ? keDecompData : keDecompFallback} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <Bar dataKey="rf"  name="Risk-Free Rate (Rf)" stackId="ke" fill="hsl(152 60% 50%)" radius={[0,0,0,0]} />
                  <Bar dataKey="erp" name="Beta × ERP"          stackId="ke" fill={GOLD}             radius={[3,3,0,0]} />
                  <Line type="monotone" dataKey="ke" name="Total Ke" stroke={NAVY} strokeWidth={2.5} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Beta Distribution" subtitle="Systematic risk across index companies" live={betaAgg.length > 0}>
            {loading ? <Skeleton /> : (() => {
              const betas = (multiMetrics.data["Calc Beta"] || []).filter(r => r.value !== null && r.value > 0 && r.value < 3).map(r => r.value!);
              const bins: { range: string; count: number }[] = [];
              for (let i = 0; i <= 2.5; i += 0.25) {
                const lo = i, hi = i + 0.25;
                bins.push({ range: `${lo.toFixed(2)}`, count: betas.filter(b => b >= lo && b < hi).length });
              }
              const fallbackBins = [
                { range: "0.25", count: 2 }, { range: "0.50", count: 8 }, { range: "0.75", count: 22 },
                { range: "1.00", count: 45 }, { range: "1.25", count: 38 }, { range: "1.50", count: 28 },
                { range: "1.75", count: 15 }, { range: "2.00", count: 7 }, { range: "2.25", count: 3 },
              ];
              const data = betas.length > 10 ? bins.filter(b => b.count > 0) : fallbackBins;
              return (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
                    onClick={(d) => { if (d?.activePayload?.[0]?.payload) drill.drillIntoSector(d.activePayload[0].payload.range); }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                    <XAxis dataKey="range" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} label={{ value: "Beta", position: "insideBottom", offset: -2, fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 8 }} tickLine={false} axisLine={false} label={{ value: "Count", angle: -90, position: "insideLeft", fontSize: 9 }} width={32} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" name="Companies" fill={NAVY} radius={[3, 3, 0, 0]} maxBarSize={28} cursor="pointer" />
                    <ReferenceLine x="1.00" stroke={GOLD} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "β=1", fill: GOLD, fontSize: 8 }} />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>

          {/* Ke vs TSR scatter */}
          <ChartCard title="Ke vs TSR — Wealth Creation" subtitle="TSR above Ke = wealth creation; below = destruction" live={tsrAgg.length > 0 && keAgg.length > 0}>
            {loading ? <Skeleton h={180} /> : (() => {
              const scatter = keAgg.map(ke => {
                const tsr = tsrAgg.find(t => t.year === ke.year);
                return tsr ? { ke: +(ke.value * 100).toFixed(1), tsr: +(tsr.value * 100).toFixed(1), year: ke.year } : null;
              }).filter(Boolean) as { ke: number; tsr: number; year: number }[];
              const fallback = [
                { ke: 9.2, tsr: 12.4 }, { ke: 9.8, tsr: -3.2 }, { ke: 10.0, tsr: 15.8 },
                { ke: 9.5, tsr: 8.7 },  { ke: 8.8, tsr: 20.1 }, { ke: 9.1, tsr: 6.2 },
              ];
              const data = scatter.length > 3 ? scatter : fallback;
              return (
                <ResponsiveContainer width="100%" height={180}>
                  <ScatterChart margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 93%)" />
                    <XAxis type="number" dataKey="ke" name="Ke" tick={{ fontSize: 8 }} tickFormatter={v => `${v}%`} domain={["auto", "auto"]} width={36} label={{ value: "Ke (%)", position: "insideBottom", offset: -8, fontSize: 9 }} />
                    <YAxis type="number" dataKey="tsr" name="TSR" tick={{ fontSize: 8 }} tickFormatter={v => `${v}%`} width={36} />
                    <ZAxis range={[60, 60]} />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<CustomTooltip />} />
                    <ReferenceLine y={0} stroke="hsl(0 60% 55%)" strokeDasharray="4 3" />
                    <Scatter name="Year" data={data} fill={NAVY} opacity={0.75} />
                  </ScatterChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>

          {/* Parameter summary */}
          <ChartCard title="Active Parameters" subtitle="CAPM inputs for current computation">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {[
                { label: "Ke Approach",   value: ctx.params?.cost_of_equity_approach || "Floating" },
                { label: "Equity Risk Premium", value: `${ctx.params?.equity_risk_premium || 5.0}%` },
                { label: "Beta Rounding", value: `${ctx.params?.beta_rounding || 0.1} decimal places` },
                { label: "Rf Rounding",   value: `${ctx.params?.risk_free_rate_rounding || 0.5}%` },
                { label: "Terminal Year", value: String(ctx.params?.terminal_year || 60) },
                { label: "Country",       value: String(ctx.params?.country || "Australia") },
              ].map(p => (
                <div key={p.label} style={{ display: "flex", justifyContent: "space-between", padding: "0.35rem 0.5rem", background: "hsl(213 40% 97%)", borderRadius: 6, border: "1px solid hsl(213 30% 90%)" }}>
                  <span style={{ fontSize: "0.6875rem", color: SLATE, fontWeight: 500 }}>{p.label}</span>
                  <span style={{ fontSize: "0.6875rem", fontWeight: 700, color: NAVY }}>{ctx.loading ? "…" : p.value}</span>
                </div>
              ))}
            </div>
          </ChartCard>
        </div>
      )}

      {/* Tab 1.2: Financial & Capital Bridge */}
      {tab === 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <ChartCard title="M:B Ratio Over Time" subtitle="Market-to-Book: Market Cap / Economic Equity" live={mbRatioFiltered.length > 0}>
            {loading || mbRatio.loading ? <Skeleton /> : (() => {
              const fallback = [
                { year: "2010", median: 2.1 }, { year: "2012", median: 2.4 }, { year: "2014", median: 2.8 },
                { year: "2016", median: 3.1 }, { year: "2018", median: 3.4 }, { year: "2020", median: 2.9 },
                { year: "2022", median: 3.5 }, { year: "2024", median: 3.7 },
              ];
              const data = mbByYear && mbByYear.length > 3 ? mbByYear : fallback;
              return (
                <ResponsiveContainer width="100%" height={220}>
                  <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}×`} width={36} />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={1} stroke={GOLD} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "Book", fill: GOLD, fontSize: 9 }} />
                    <Area type="monotone" dataKey="median" name="M:B Ratio (median)" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>

          <ChartCard title="ROEE vs Cost of Equity" subtitle="Return on Economic Equity vs Ke hurdle (%)" live={roeeFiltered.length > 0}>
            {loading || roee.loading ? <Skeleton /> : (() => {
              // Build per-ticker time series lines
              const tickerData: Record<string, { year: string; value: number }[]> = {};
              roeeFiltered.slice(0, 6).forEach(r => {
                tickerData[r.ticker] = (r.time_series || [])
                  .filter(ts => ts.value !== null)
                  .slice(-8)
                  .map(ts => ({ year: String(ts.year), value: +(ts.value! * 100).toFixed(1) }));
              });
              const allYears = Array.from(new Set(
                Object.values(tickerData).flat().map(d => d.year)
              )).sort();
              const chartData = allYears.map(year => {
                const row: any = { year };
                Object.entries(tickerData).forEach(([ticker, series]) => {
                  const pt = series.find(s => s.year === year);
                  if (pt) row[ticker] = pt.value;
                });
                return row;
              });
              const tickers = Object.keys(tickerData);
              const fallback = [
                { year: "2015", BHP: 12.1, CBA: 15.4, WBC: 14.2, CSL: 28.1 },
                { year: "2017", BHP: 9.8,  CBA: 14.8, WBC: 13.5, CSL: 30.2 },
                { year: "2019", BHP: 11.2, CBA: 12.1, WBC: 11.8, CSL: 32.5 },
                { year: "2021", BHP: 18.4, CBA: 13.9, WBC: 10.2, CSL: 24.8 },
                { year: "2023", BHP: 14.2, CBA: 14.5, WBC: 11.8, CSL: 26.1 },
              ];
              const finalData = chartData.length > 2 ? chartData : fallback;
              const finalTickers = tickers.length > 0 ? tickers : ["BHP", "CBA", "WBC", "CSL"];
              return (
                <ResponsiveContainer width="100%" height={220}>
                  <ComposedChart data={finalData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                    <ReferenceLine y={10} stroke={GOLD} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "Ke~10%", fill: GOLD, fontSize: 8 }} />
                    {finalTickers.slice(0, 5).map((t: string, i: number) => (
                      <Line key={t} type="monotone" dataKey={t} stroke={CHART_COLORS[i]} strokeWidth={1.8} dot={false}
                        activeDot={{ r: 5, cursor: "pointer", onClick: () => drill.drillIntoTicker(t) }} />
                    ))}
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>

          <ChartCard title="Operating Cost Margin by Sector" subtitle="Op Cost / Revenue — efficiency indicator (%)" live={opCostFiltered.length > 0}>
            {loading || opCost.loading ? <Skeleton h={200} /> : (() => {
              const sectorData: Record<string, number[]> = {};
              opCostFiltered.forEach(r => {
                const lastVal = r.time_series?.slice(-1)?.[0]?.value;
                if (lastVal !== null && lastVal !== undefined) {
                  const sector = r.sector || "Other";
                  if (!sectorData[sector]) sectorData[sector] = [];
                  sectorData[sector].push(lastVal * 100);
                }
              });
              const chartData = Object.entries(sectorData).map(([sector, vals]) => ({
                sector: sector.length > 14 ? sector.slice(0, 12) + "…" : sector,
                fullSector: sector,
                value: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1),
              })).sort((a, b) => b.value - a.value).slice(0, 8);
              const fallback = [
                { sector: "Materials",  fullSector: "Materials",  value: 62.1 },
                { sector: "Financials", fullSector: "Financials", value: 45.2 },
                { sector: "Energy",     fullSector: "Energy",     value: 58.4 },
                { sector: "Health Care",fullSector: "Health Care",value: 52.3 },
                { sector: "Industrials",fullSector: "Industrials",value: 67.8 },
                { sector: "IT",         fullSector: "IT",         value: 38.5 },
                { sector: "Consumer",   fullSector: "Consumer",   value: 71.2 },
                { sector: "Utilities",  fullSector: "Utilities",  value: 55.8 },
              ];
              const data = chartData.length > 3 ? chartData : fallback;
              return (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 0 }}
                    onClick={(d) => { if (d?.activePayload?.[0]?.payload?.fullSector) drill.drillIntoSector(d.activePayload[0].payload.fullSector); }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(210 16% 93%)" />
                    <XAxis type="number" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                    <YAxis type="category" dataKey="sector" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} width={70} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" name="Op Cost Margin (%)" fill={GOLD} radius={[0, 4, 4, 0]} maxBarSize={16} cursor="pointer" />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>

          <ChartCard title="Effective Tax Rate" subtitle="Actual tax burden vs statutory rate (%)" live={etrFiltered.length > 0}>
            {loading || etr.loading ? <Skeleton h={200} /> : (() => {
              const etrAgg: Record<number, number[]> = {};
              etrFiltered.forEach(r => {
                (r.time_series || []).forEach(ts => {
                  if (!etrAgg[ts.year]) etrAgg[ts.year] = [];
                  if (ts.value !== null) etrAgg[ts.year].push(ts.value * 100);
                });
              });
              const data = Object.entries(etrAgg).map(([year, vals]: [string, any]) => ({
                year,
                value: +(vals.reduce((a: number, b: number) => a + b, 0) / vals.length).toFixed(1),
              })).sort((a, b) => a.year.localeCompare(b.year)).slice(-12);
              const fallback = [
                { year: "2015", value: 28.1 }, { year: "2016", value: 27.8 }, { year: "2017", value: 28.5 },
                { year: "2018", value: 27.2 }, { year: "2019", value: 26.8 }, { year: "2020", value: 25.4 },
                { year: "2021", value: 26.1 }, { year: "2022", value: 27.5 }, { year: "2023", value: 28.2 },
              ];
              const finalData = data.length > 3 ? data : fallback;
              return (
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={finalData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={30} stroke={SLATE} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "30% statutory", fill: SLATE, fontSize: 8 }} />
                    <Bar dataKey="value" name="Effective Tax Rate (%)" fill={NAVY} radius={[3, 3, 0, 0]} maxBarSize={28} />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>
        </div>
      )}

      {/* Tabs 1.3–1.5: illustrative charts */}
      {tab >= 2 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {[
            { title: "Products & Services Market — EP vs EPS Performance", subtitle: "EP-dominant vs EPS-dominant cohort 10yr TSR comparison" },
            { title: "Capital Market Predictor — Regression Analysis", subtitle: "Predictive relationship: EP → Market Value" },
            { title: "Capital Market Assessment — Sector EP Scores", subtitle: "Sector-level economic profitability index" },
            { title: "TSR Composition — Price Return vs Dividend", subtitle: "Decomposition of total shareholder return" },
          ].slice(0, 2).map((c, i) => (
            <ChartCard key={i} title={c.title} subtitle={c.subtitle} live={false}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={[
                  { label: "EP Dom.", val1: 14.8, val2: 5.7 },
                  { label: "EPS Dom.", val1: 5.7, val2: 14.8 },
                  { label: "Mixed", val1: 9.2, val2: 9.2 },
                ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                  <XAxis dataKey="label" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <Bar dataKey="val1" name="10yr TSR (%)" fill={NAVY} radius={[3, 3, 0, 0]} />
                  <Bar dataKey="val2" name="Benchmark (%)" fill={GOLD} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          ))}
        </div>
      )}

      <style>{`
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
      `}</style>
    </div>
  );
}
