/**
 * Principle 3 — Capital Market Returns
 * Live data: Calc 1Y/3Y/5Y/10Y TER, Calc 1Y/3Y/5Y/10Y TER-KE, Calc 1Y/3Y/5Y/10Y TER Alpha, ECF, FY TSR
 */
import { useState, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import {
  ComposedChart, BarChart, AreaChart,
  Area, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useActiveContext, useMultipleMetrics, aggregateByYear } from "../hooks/useMetrics";
import { useDrillDown, DrillDownBanner } from "../context/DrillDown";
import { RollingTimeSeries } from "../components/RollingTimeSeries";
import { buildRollingFromWindowed } from "../lib/rollingAverage";

const NAVY = "hsl(213 75% 22%)"; const GOLD = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)"; const SLATE = "hsl(215 15% 46%)";
const RED = "hsl(0 60% 50%)";

const T = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#fff", border: "1px solid hsl(210 16% 88%)", borderRadius: 8, padding: "0.5rem 0.75rem", boxShadow: "0 4px 16px rgba(0,0,0,0.1)", fontSize: "0.75rem" }}>
      <div style={{ fontWeight: 700, marginBottom: "0.2rem" }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color, display: "flex", gap: "0.4rem" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, marginTop: 3, flexShrink: 0, display: "inline-block" }} />
          <span>{p.name}: <b>{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</b></span>
        </div>
      ))}
    </div>
  );
};

function Card({ title, sub, live, children }: { title: string; sub?: string; live?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 10, border: "1px solid hsl(210 16% 90%)", padding: "1rem 1.25rem", boxShadow: "0 1px 4px hsl(213 40% 50% / 0.05)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.875rem" }}>
        <div>
          <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(220 35% 12%)" }}>{title}</div>
          {sub && <div style={{ fontSize: "0.6875rem", color: SLATE, marginTop: "0.125rem" }}>{sub}</div>}
        </div>
        {live !== undefined && (
          <span style={{ fontSize: "0.5625rem", fontWeight: 700, padding: "0.15rem 0.45rem", background: live ? "hsl(152 60% 40% / 0.1)" : "hsl(38 60% 52% / 0.1)", color: live ? "hsl(152 50% 30%)" : "hsl(38 60% 35%)", borderRadius: 999, border: live ? "1px solid hsl(152 60% 40% / 0.3)" : "1px solid hsl(38 60% 52% / 0.3)", textTransform: "uppercase" }}>
            {live ? "● LIVE" : "ILLUS."}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function Skel({ h = 200 }: { h?: number }) {
  return <div style={{ height: h, background: "hsl(210 20% 95%)", borderRadius: 8, animation: "shimmer 1.4s infinite", backgroundImage: "linear-gradient(90deg,hsl(210 20% 95%),hsl(210 20% 92%),hsl(210 20% 95%))", backgroundSize: "200% 100%" }} />;
}

export default function PrincipleThreePage() {
  const params = useParams<{ tab?: string }>();
  const [, navigate] = useLocation();
  const drill = useDrillDown();
  const TAB_IDS_P3 = ["3.1", "3.2", "3.3", "3.4", "3.5"];
  const tabFromUrl = params.tab ? TAB_IDS_P3.indexOf(params.tab) : -1;
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0);
  useEffect(() => {
    const idx = params.tab ? TAB_IDS_P3.indexOf(params.tab) : -1;
    if (idx >= 0) setTab(idx);
  }, [params.tab]);
  const handleTabClick = (i: number) => { setTab(i); navigate(`/principles/3/${TAB_IDS_P3[i]}`); };
  const ctx = useActiveContext();
  const metrics = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, [
    "Calc 1Y TER", "Calc 3Y TER", "Calc 5Y TER", "Calc 10Y TER",
    "Calc 1Y TER-KE", "Calc 3Y TER-KE", "Calc 5Y TER-KE", "Calc 10Y TER-KE",
    "Calc 1Y TER Alpha", "Calc 3Y TER Alpha", "Calc 5Y TER Alpha", "Calc 10Y TER Alpha",
    "Calc ECF", "Non Div ECF", "Calc FY TSR",
  ]);
  const loading = ctx.loading || metrics.loading;

  const ter1   = aggregateByYear(metrics.data["Calc 1Y TER"]     || []);
  const ter3   = aggregateByYear(metrics.data["Calc 3Y TER"]     || []);
  const ter5   = aggregateByYear(metrics.data["Calc 5Y TER"]     || []);
  const ter10  = aggregateByYear(metrics.data["Calc 10Y TER"]    || []);
  const terKe1 = aggregateByYear(metrics.data["Calc 1Y TER-KE"]  || []);
  const terKe3 = aggregateByYear(metrics.data["Calc 3Y TER-KE"]  || []);
  const terKe5 = aggregateByYear(metrics.data["Calc 5Y TER-KE"]  || []);
  const terKe10= aggregateByYear(metrics.data["Calc 10Y TER-KE"] || []);
  const alpha1 = aggregateByYear(metrics.data["Calc 1Y TER Alpha"]  || []);
  const alpha3 = aggregateByYear(metrics.data["Calc 3Y TER Alpha"]  || []);

  // Build RollingRow[] for TER-Ke rolling time series
  const terKeRollingRows = buildRollingFromWindowed(
    terKe1.map(d => ({ year: d.year, value: d.value })),
    terKe3.map(d => ({ year: d.year, value: d.value })),
    terKe5.map(d => ({ year: d.year, value: d.value })),
    terKe10.map(d => ({ year: d.year, value: d.value })),
    100, // values stored as decimals, ×100 for %
  );

  // Build RollingRow[] for TER Alpha rolling time series
  const alpha5  = aggregateByYear(metrics.data["Calc 5Y TER Alpha"]  || []);
  const alpha10 = aggregateByYear(metrics.data["Calc 10Y TER Alpha"] || []);
  const alphaRollingRows = buildRollingFromWindowed(
    alpha1.map(d => ({ year: d.year, value: d.value })),
    alpha3.map(d => ({ year: d.year, value: d.value })),
    alpha5.map(d => ({ year: d.year, value: d.value })),
    alpha10.map(d => ({ year: d.year, value: d.value })),
    100,
  );

  // Build RollingRow[] for TER rolling time series
  const terRollingRows = buildRollingFromWindowed(
    ter1.map(d => ({ year: d.year, value: d.value })),
    ter3.map(d => ({ year: d.year, value: d.value })),
    ter5.map(d => ({ year: d.year, value: d.value })),
    ter10.map(d => ({ year: d.year, value: d.value })),
    100,
  );
  const ecf    = aggregateByYear(metrics.data["Calc ECF"]      || []);
  const nonDiv = aggregateByYear(metrics.data["Non Div ECF"]   || []);
  const tsr    = aggregateByYear(metrics.data["Calc FY TSR"]   || []);

  // Build TER multi-window chart
  const terMultiWindow = ter1.map(d => {
    const t3 = ter3.find(x => x.year === d.year)?.value ?? null;
    const t5 = ter5.find(x => x.year === d.year)?.value ?? null;
    const t10 = ter10.find(x => x.year === d.year)?.value ?? null;
    return { year: String(d.year), "1Y": +(d.value * 100).toFixed(2), "3Y": t3 ? +(t3 * 100).toFixed(2) : null, "5Y": t5 ? +(t5 * 100).toFixed(2) : null, "10Y": t10 ? +(t10 * 100).toFixed(2) : null };
  }).slice(-15);

  const isLiveTER = terMultiWindow.length > 3;

  // TER-Ke chart
  const terKeChart = terKe1.map(d => ({
    year: String(d.year),
    terKe1Y:  +(d.value * 100).toFixed(2),
    terKe3Y:  (terKe3.find(x => x.year === d.year)?.value ?? null) !== null ? +((terKe3.find(x => x.year === d.year)!.value) * 100).toFixed(2) : null,
    terKe10Y: (terKe10.find(x => x.year === d.year)?.value ?? null) !== null ? +((terKe10.find(x => x.year === d.year)!.value) * 100).toFixed(2) : null,
  })).slice(-15);

  // TER Alpha
  const alphaChart = alpha1.map(d => ({
    year: String(d.year),
    alpha1: +(d.value * 100).toFixed(2),
    alpha3: (alpha3.find(x => x.year === d.year)?.value ?? null) !== null ? +((alpha3.find(x => x.year === d.year)!.value) * 100).toFixed(2) : null,
  })).slice(-15);

  // ECF decomposition
  const ecfChart = ecf.map(d => {
    const nd = nonDiv.find(x => x.year === d.year);
    return {
      year: String(d.year),
      dividend: +(((nd ? d.value - nd.value : d.value * 0.4) / 1e6).toFixed(1)),
      retained: +((nd ? nd.value / 1e6 : d.value * 0.6 / 1e6).toFixed(1)),
    };
  }).slice(-15);

  const fallbackTER = [
    { year: "2010", "1Y": 8.2, "3Y": 9.4, "5Y": 10.1, "10Y": 11.8 },
    { year: "2013", "1Y": 9.8, "3Y": 10.5,"5Y": 11.2, "10Y": 12.4 },
    { year: "2016", "1Y": 7.1, "3Y": 8.9, "5Y": 10.4, "10Y": 11.5 },
    { year: "2019", "1Y": 6.2, "3Y": 8.4, "5Y": 9.8,  "10Y": 11.0 },
    { year: "2022", "1Y": 10.4,"3Y": 9.8, "5Y": 10.2, "10Y": 11.2 },
    { year: "2024", "1Y": 8.8, "3Y": 9.2, "5Y": 9.9,  "10Y": 10.8 },
  ];

  const tabs = ["3.1  TER & TSR", "3.2  TER Alpha", "3.3  ECF Decomposition", "3.4  International TER", "3.5  Wealth Creation ($B)"];

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1600 }}>
      <DrillDownBanner />
      <div>
        <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
          Principle 3 — Capital Market Returns
        </h1>
        <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0" }}>
          TER · TER-Ke · TER Alpha · ECF Decomposition · Wealth Creation
        </p>
      </div>
      <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
        {tabs.map((t, i) => (
          <button key={i} onClick={() => handleTabClick(i)} style={{ padding: "0.35rem 0.75rem", background: tab === i ? NAVY : "transparent", color: tab === i ? "#fff" : SLATE, border: `1px solid ${tab === i ? NAVY : "hsl(210 16% 88%)"}`, borderRadius: 6, fontSize: "0.6875rem", fontWeight: tab === i ? 700 : 500, cursor: "pointer" }}>{t}</button>
        ))}
      </div>

      {/* Tab 3.1: TER & TSR */}
      {tab === 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <Card title="TER by Annualisation Window" sub="1Y · 3Y · 5Y · 10Y annualised total equity return (%)" live={isLiveTER}>
              {loading ? <Skel /> : (
                <ResponsiveContainer width="100%" height={230}>
                  <ComposedChart data={isLiveTER ? terMultiWindow : fallbackTER} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                    <Tooltip content={<T />} />
                    <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                    <ReferenceLine y={10} stroke={SLATE} strokeDasharray="3 3" strokeWidth={1} label={{ value: "Ke~10%", fill: SLATE, fontSize: 8 }} />
                    <Line type="monotone" dataKey="1Y"  name="TER 1Y"  stroke={NAVY} strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="3Y"  name="TER 3Y"  stroke={GOLD} strokeWidth={2}   dot={false} />
                    <Line type="monotone" dataKey="5Y"  name="TER 5Y"  stroke={GREEN} strokeWidth={1.8} dot={false} strokeDasharray="4 3" />
                    <Line type="monotone" dataKey="10Y" name="TER 10Y" stroke="hsl(280 55% 50%)" strokeWidth={1.8} dot={false} strokeDasharray="2 2" />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="TER-Ke — Wealth Creation Component" sub="TER minus Cost of Equity: positive = wealth created (%)" live={terKeChart.length > 3}>
              {loading ? <Skel /> : (() => {
                const fallback = [
                  { year: "2010", terKe1Y: 1.8, terKe3Y: 2.1, terKe10Y: 2.8 },
                  { year: "2013", terKe1Y: 3.2, terKe3Y: 3.4, terKe10Y: 2.4 },
                  { year: "2016", terKe1Y: -0.4, terKe3Y: 1.2, terKe10Y: 1.5 },
                  { year: "2019", terKe1Y: -1.2, terKe3Y: 0.8, terKe10Y: 1.0 },
                  { year: "2022", terKe1Y: 3.8, terKe3Y: 2.6, terKe10Y: 1.2 },
                  { year: "2024", terKe1Y: 1.2, terKe3Y: 1.8, terKe10Y: 0.8 },
                ];
                const data = terKeChart.length > 3 ? terKeChart : fallback;
                return (
                  <ResponsiveContainer width="100%" height={230}>
                    <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                      <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                      <Tooltip content={<T />} />
                      <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                      <ReferenceLine y={0} stroke={RED} strokeDasharray="4 3" strokeWidth={1.5} />
                      <Area type="monotone" dataKey="terKe1Y"  name="TER-Ke 1Y"  stroke={NAVY} fill="hsl(213 75% 22% / 0.1)" strokeWidth={2.5} dot={false} />
                      <Line  type="monotone" dataKey="terKe3Y"  name="TER-Ke 3Y"  stroke={GOLD} strokeWidth={2} dot={false} strokeDasharray="5 3" />
                      <Line  type="monotone" dataKey="terKe10Y" name="TER-Ke 10Y" stroke={GREEN} strokeWidth={1.8} dot={false} strokeDasharray="2 2" />
                    </ComposedChart>
                  </ResponsiveContainer>
                );
              })()}
            </Card>
          </div>

          {/* Rolling averages row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <Card title="TER Rolling Averages" sub="1Y/3Y/5Y/10Y/LT cross-sectional rolling average (%)" live={terRollingRows.length > 0}>
              <RollingTimeSeries title="" rows={terRollingRows} valueFormat="pct" bare />
            </Card>
            <Card title="TER-Ke Rolling Averages" sub="Wealth creation spread — rolling average (%)" live={terKeRollingRows.length > 0}>
              <RollingTimeSeries title="" rows={terKeRollingRows} valueFormat="pct" bare />
            </Card>
          </div>
        </div>
      )}

      {/* Tab 3.2: TER Alpha */}
      {tab === 1 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <Card title="TER Alpha — Risk-Adjusted Outperformance" sub="TER-Ke minus Risk-Adjusted Market Movement (RA_MM)" live={alphaChart.length > 3}>
            {loading ? <Skel h={240} /> : (() => {
              const fallback = [
                { year: "2010", alpha1: 1.2, alpha3: 1.5 }, { year: "2012", alpha1: 0.8, alpha3: 1.2 },
                { year: "2014", alpha1: -0.4, alpha3: 0.6 }, { year: "2016", alpha1: 1.8, alpha3: 1.1 },
                { year: "2018", alpha1: 0.4, alpha3: 0.9 }, { year: "2020", alpha1: -1.2, alpha3: 0.2 },
                { year: "2022", alpha1: 2.1, alpha3: 1.4 }, { year: "2024", alpha1: 0.6, alpha3: 0.8 },
              ];
              const data = alphaChart.length > 3 ? alphaChart : fallback;
              return (
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                    <Tooltip content={<T />} />
                    <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                    <ReferenceLine y={0} stroke={RED} strokeDasharray="4 3" />
                    <Area type="monotone" dataKey="alpha1" name="TER Alpha 1Y" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2.5} dot={false} />
                    <Line  type="monotone" dataKey="alpha3" name="TER Alpha 3Y" stroke={GOLD} strokeWidth={2} dot={false} strokeDasharray="5 3" />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>

          <Card title="TER Alpha Distribution (1Y)" sub="Frequency of positive vs negative alpha outcomes" live={alpha1.length > 10}>
            {loading ? <Skel h={240} /> : (() => {
              const rawAlpha = metrics.data["Calc 1Y TER Alpha"] || [];
              const bins: Record<string, number> = {};
              rawAlpha.filter(r => r.value !== null).forEach(r => {
                const v = r.value! * 100;
                const bin = `${(Math.floor(v / 2) * 2).toFixed(0)}`;
                bins[bin] = (bins[bin] || 0) + 1;
              });
              const sorted = Object.entries(bins).map(([range, count]) => ({ range, count })).sort((a, b) => Number(a.range) - Number(b.range));
              const fallback = [
                { range: "-8", count: 2 }, { range: "-6", count: 5 }, { range: "-4", count: 12 },
                { range: "-2", count: 22 }, { range: "0", count: 35 }, { range: "2", count: 28 },
                { range: "4", count: 18 }, { range: "6", count: 10 }, { range: "8", count: 4 },
              ];
              const data = sorted.length > 5 ? sorted : fallback;
              return (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                    <XAxis dataKey="range" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} label={{ value: "TER Alpha (%)", position: "insideBottom", offset: -4, fontSize: 9 }} />
                    <YAxis tick={{ fontSize: 8 }} tickLine={false} axisLine={false} width={28} />
                    <Tooltip content={<T />} />
                    <Bar dataKey="count" name="Companies" fill={NAVY} radius={[3, 3, 0, 0]} maxBarSize={24} />
                    <ReferenceLine x="0" stroke={RED} strokeDasharray="3 3" />
                  </BarChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>
          </div>

          {/* TER Alpha rolling averages */}
          <Card title="TER Alpha Rolling Averages" sub="Risk-adjusted outperformance — 1Y/3Y/5Y/10Y/LT rolling average (%)" live={alphaRollingRows.length > 0}>
            <RollingTimeSeries title="" rows={alphaRollingRows} valueFormat="pct" bare />
          </Card>
        </div>
      )}

      {/* Tab 3.3: ECF */}
      {tab === 2 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <Card title="ECF Decomposition — Dividend vs Retained" sub={ecfChart.length > 3 ? "Live: Dividend ECF vs Non-Dividend ECF ($m)" : "Illustrative"} live={ecfChart.length > 3}>
            {loading ? <Skel h={230} /> : (() => {
              const fallback = [
                { year: "2015", dividend: 85, retained: 95 }, { year: "2017", dividend: 98, retained: 127 },
                { year: "2019", dividend: 88, retained: 127 }, { year: "2021", dividend: 95, retained: 153 },
                { year: "2023", dividend: 128, retained: 184 },
              ];
              const data = ecfChart.length > 3 ? ecfChart : fallback;
              return (
                <ResponsiveContainer width="100%" height={230}>
                  <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v}m`} width={44} />
                    <Tooltip content={<T />} />
                    <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                    <Area type="monotone" dataKey="retained" name="Non-Div ECF ($m)" stackId="ecf" stroke={NAVY} fill="hsl(213 75% 22% / 0.15)" strokeWidth={1.5} dot={false} />
                    <Area type="monotone" dataKey="dividend" name="Dividend ECF ($m)" stackId="ecf" stroke={GOLD} fill="hsl(38 60% 52% / 0.15)" strokeWidth={1.5} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>

          <Card title="FY TSR vs TER over Time" sub={tsr.length > 3 ? "Live TSR vs TER comparison" : "Illustrative: TSR and TER alignment"} live={tsr.length > 3}>
            {loading ? <Skel h={230} /> : (() => {
              const terTsrData = tsr.map(d => {
                const terVal = ter1.find(t => t.year === d.year)?.value;
                return { year: String(d.year), tsr: +(d.value * 100).toFixed(2), ter: terVal ? +(terVal * 100).toFixed(2) : null };
              }).slice(-15);
              const fallback = [
                { year: "2010", tsr: 14.2, ter: 12.8 }, { year: "2013", tsr: 18.4, ter: 16.2 },
                { year: "2016", tsr: 7.8, ter: 8.4 }, { year: "2019", tsr: 6.2, ter: 7.1 },
                { year: "2022", tsr: 12.4, ter: 11.8 }, { year: "2024", tsr: 9.8, ter: 9.2 },
              ];
              const data = terTsrData.length > 3 ? terTsrData : fallback;
              return (
                <ResponsiveContainer width="100%" height={230}>
                  <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                    <Tooltip content={<T />} />
                    <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                    <Line type="monotone" dataKey="tsr" name="FY TSR (%)" stroke={NAVY} strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="ter" name="TER 1Y (%)"  stroke={GOLD} strokeWidth={2} strokeDasharray="5 3" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </Card>
        </div>
      )}

      {/* Tab 3.4: International TER */}
      {tab === 3 && (
        <Card title="International TER Comparison — AUS vs USA vs UK" sub="TER-Ke across major indices: positive = market creating wealth above cost of equity (illustrative)" live={false}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={[
              { year: "2005", aus: 3.2, usa: 4.8, uk: 1.8 }, { year: "2007", aus: 8.1, usa: 9.2, uk: 5.4 },
              { year: "2009", aus: -6.2, usa: -14.1, uk: -8.4 }, { year: "2011", aus: 2.1, usa: 1.8, uk: -0.8 },
              { year: "2013", aus: 4.8, usa: 7.2, uk: 3.4 }, { year: "2015", aus: 1.2, usa: 4.1, uk: 0.8 },
              { year: "2017", aus: 3.8, usa: 6.8, uk: 2.1 }, { year: "2019", aus: 1.4, usa: 5.2, uk: 0.4 },
              { year: "2021", aus: 5.4, usa: 8.8, uk: 4.2 }, { year: "2023", aus: 2.1, usa: 4.8, uk: 1.4 },
            ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
              <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
              <Tooltip content={<T />} />
              <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
              <ReferenceLine y={0} stroke={RED} strokeDasharray="4 3" />
              <Area type="monotone" dataKey="aus" name="ASX 200 TER-Ke" stroke={NAVY} fill="hsl(213 75% 22% / 0.1)" strokeWidth={2.5} dot={false} />
              <Line  type="monotone" dataKey="usa" name="S&P 500 TER-Ke" stroke={GREEN} strokeWidth={2} dot={false} />
              <Line  type="monotone" dataKey="uk"  name="FTSE 100 TER-Ke" stroke={GOLD} strokeWidth={2} strokeDasharray="5 3" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Tab 3.5: Wealth Creation $B */}
      {tab === 4 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <Card title="Wealth Creation ($B) — Annual ASX 300" sub="Total wealth created by the index (WC + WP = absolute return, $B)" live={false}>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={[
                { year: "2005", wc: 145, wp: 210 }, { year: "2007", wc: 285, wp: 240 },
                { year: "2009", wc: -380, wp: 180 }, { year: "2011", wc: 95, wp: 220 },
                { year: "2013", wc: 210, wp: 250 }, { year: "2015", wc: 120, wp: 245 },
                { year: "2017", wc: 195, wp: 265 }, { year: "2019", wc: 85, wp: 260 },
                { year: "2021", wc: 310, wp: 290 }, { year: "2023", wc: 148, wp: 285 },
              ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v}B`} width={44} />
                <Tooltip content={<T />} />
                <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                <ReferenceLine y={0} stroke={RED} strokeWidth={1} />
                <Bar dataKey="wp" name="Wealth Preservation ($B)" stackId="w" fill="hsl(213 40% 75%)" radius={[0, 0, 0, 0]} />
                <Bar dataKey="wc" name="Wealth Creation ($B)"     stackId="w" fill={NAVY} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="WC_TERA — Risk-Adjusted Wealth Creation ($B)" sub="Strips passive market tailwind: only company-driven alpha ($B)" live={false}>
            <ResponsiveContainer width="100%" height={250}>
              <ComposedChart data={[
                { year: "2005", wcTera: 82, wcRa: 145 }, { year: "2007", wcTera: 148, wcRa: 285 },
                { year: "2009", wcTera: -280, wcRa: -380 }, { year: "2011", wcTera: 48, wcRa: 95 },
                { year: "2013", wcTera: 125, wcRa: 210 }, { year: "2015", wcTera: 65, wcRa: 120 },
                { year: "2017", wcTera: 108, wcRa: 195 }, { year: "2019", wcTera: 42, wcRa: 85 },
                { year: "2021", wcTera: 195, wcRa: 310 }, { year: "2023", wcTera: 88, wcRa: 148 },
              ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v}B`} width={44} />
                <Tooltip content={<T />} />
                <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                <ReferenceLine y={0} stroke={RED} strokeDasharray="4 3" />
                <Area type="monotone" dataKey="wcRa"   name="WC Raw ($B)"          stroke={SLATE} fill="hsl(215 15% 46% / 0.1)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                <Area type="monotone" dataKey="wcTera" name="WC_TERA ($B — risk adj.)" stroke={NAVY} fill="hsl(213 75% 22% / 0.15)" strokeWidth={2.5} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      <style>{`@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}`}</style>
    </div>
  );
}
