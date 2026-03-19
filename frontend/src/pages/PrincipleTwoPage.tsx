/**
 * Principle 2 — Primary Focus on the Longer Term
 * Live data: Calc EP (bow wave), M:B Ratio, ECF
 */
import { useState, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import {
  ComposedChart, AreaChart, BarChart, LineChart,
  Area, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import { useActiveContext, useEPSeries, useMultipleMetrics, useRatioMetric, aggregateByYear, NormalizedRatioItem } from "../hooks/useMetrics";
import { useDrillDown, DrillDownBanner, applyDrillFilter } from "../context/DrillDown";

const NAVY  = "hsl(213 75% 22%)";
const GOLD  = "hsl(38 60% 52%)";
const GREEN = "hsl(152 60% 40%)";
const SLATE = "hsl(215 15% 46%)";

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: "0.35rem 0.75rem",
      background: active ? NAVY : "transparent",
      color: active ? "#fff" : SLATE,
      border: `1px solid ${active ? NAVY : "hsl(210 16% 88%)"}`,
      borderRadius: 6, fontSize: "0.6875rem", fontWeight: active ? 700 : 500,
      cursor: "pointer",
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
          }}>{live ? "● LIVE" : "ILLUS."}</span>
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
    <div style={{ background: "#fff", border: "1px solid hsl(210 16% 88%)", borderRadius: 8, padding: "0.5rem 0.75rem", boxShadow: "0 4px 16px rgba(0,0,0,0.1)", fontSize: "0.75rem" }}>
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

// Bell curve helper for bow wave
function bell(x: number, mu: number, sigma: number, peak: number) {
  return +(peak * Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma))).toFixed(2);
}

export default function PrincipleTwoPage() {
  const params = useParams<{ tab?: string }>();
  const [, navigate] = useLocation();
  const drill = useDrillDown();
  const TAB_IDS = ["2.1", "2.2", "2.3", "2.4", "2.5"];
  const tabFromUrl = params.tab ? TAB_IDS.indexOf(params.tab) : -1;
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0);
  useEffect(() => {
    const idx = params.tab ? TAB_IDS.indexOf(params.tab) : -1;
    if (idx >= 0) setTab(idx);
  }, [params.tab]);
  const handleTabClick = (i: number) => { setTab(i); navigate(`/principles/2/${TAB_IDS[i]}`); };
  const ctx = useActiveContext();

  const ep1Y  = useEPSeries(ctx.datasetId, ctx.paramSetId, "1Y");
  const ep3Y  = useEPSeries(ctx.datasetId, ctx.paramSetId, "3Y");
  const ep5Y  = useEPSeries(ctx.datasetId, ctx.paramSetId, "5Y");
  const ep10Y = useEPSeries(ctx.datasetId, ctx.paramSetId, "10Y");
  const multiMetrics = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, ["Calc ECF", "Non Div ECF", "Calc FY TSR", "Calc EE", "Calc MC"]);
  const mbRatio = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio", "1Y");

  const loading = ctx.loading || ep1Y.loading;

  // Build bow-wave from live EP
  const epAgg1Y  = aggregateByYear((ep1Y.data  || []).map(r => ({ ticker: r.ticker, fiscal_year: r.fiscal_year, value: r.ep_1y  ?? null })));
  const epAgg3Y  = aggregateByYear((ep3Y.data  || []).map(r => ({ ticker: r.ticker, fiscal_year: r.fiscal_year, value: r.ep_3y  ?? null })));
  const epAgg5Y  = aggregateByYear((ep5Y.data  || []).map(r => ({ ticker: r.ticker, fiscal_year: r.fiscal_year, value: r.ep_5y  ?? null })));
  const epAgg10Y = aggregateByYear((ep10Y.data || []).map(r => ({ ticker: r.ticker, fiscal_year: r.fiscal_year, value: r.ep_10y ?? null })));
  const isLiveEP = epAgg1Y.length >= 4;

  // Static bow wave
  const bowWaveStatic = Array.from({ length: 26 }, (_, i) => {
    const offset = i - 10;
    const yr = 2014 + offset;
    return {
      year: String(yr),
      baseline: bell(offset, 3, 6, 350),
      newExp: offset >= 0 ? bell(offset, 5, 8, 720) : null,
      pairWave: bell(offset, -2, 5, 280),
    };
  });

  // Live bow wave
  const bowWaveLive = epAgg1Y.map((d, i) => ({
    year: String(d.year),
    ep1Y: +(d.value / 1e6).toFixed(2),
    ep3Y: epAgg3Y[i] ? +(epAgg3Y[i].value / 1e6).toFixed(2) : null,
  }));

  // ECF decomposition
  const ecfAgg    = aggregateByYear(multiMetrics.data["Calc ECF"]    || []);
  const nonDivAgg = aggregateByYear(multiMetrics.data["Non Div ECF"] || []);
  const ecfChartData = ecfAgg.map(d => {
    const nonDiv = nonDivAgg.find(n => n.year === d.year);
    const divEcf = nonDiv ? d.value - nonDiv.value : d.value * 0.4;
    return {
      year: String(d.year),
      dividend: +(divEcf / 1e6).toFixed(1),
      retained: +(nonDiv ? nonDiv.value / 1e6 : d.value * 0.6 / 1e6).toFixed(1),
    };
  }).slice(-15);

  // M:B ratio time series
  const mbFiltered: NormalizedRatioItem[] = applyDrillFilter(mbRatio.data || [], drill);
  const mbData = mbFiltered.reduce((acc: Record<string, number[]>, r) => {
    (r.time_series || []).forEach(ts => {
      if (!acc[String(ts.year)]) acc[String(ts.year)] = [];
      if (ts.value !== null) acc[String(ts.year)].push(ts.value!);
    });
    return acc;
  }, {} as Record<string, number[]>);
  const mbByYear = Object.entries(mbData).map(([yr, vals]) => ({
    year: yr,
    median: +(vals.sort((a, b) => a - b)[Math.floor(vals.length / 2)]).toFixed(2),
  })).sort((a, b) => a.year.localeCompare(b.year)).slice(-15);

  const tabs = ["2.1  Market Value & EP", "2.2  Bow Wave Concept", "2.3  Pair of EP Bow Waves", "2.4  Long-Term Proof", "2.5  Wealth Reconciliation"];

  return (
    <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 1600 }}>
      <DrillDownBanner />
      <div>
        <h1 style={{ fontSize: "1.125rem", fontWeight: 800, color: "hsl(220 35% 12%)", margin: 0, letterSpacing: "-0.02em" }}>
          Principle 2 — Primary Focus on the Longer Term
        </h1>
        <p style={{ fontSize: "0.75rem", color: SLATE, margin: "0.25rem 0 0" }}>
          EP Bow Wave · Market Value · Pair of Bow Waves · Long-Term Focus Proof
        </p>
      </div>

      <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
        {tabs.map((t, i) => <Chip key={i} label={t} active={tab === i} onClick={() => handleTabClick(i)} />)}
      </div>

      {/* Tab 2.1: Market Value & EP */}
      {tab === 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1rem" }}>
          <ChartCard title="EP over Time — Market Value Proxy" subtitle={isLiveEP ? "Live Calc EP aggregated across index (avg, $m)" : "Illustrative: EP is the primary driver of market value"} live={isLiveEP}>
            {loading ? <Skeleton h={240} /> : (
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={isLiveEP ? bowWaveLive : bowWaveStatic} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={40} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <ReferenceLine y={0} stroke="hsl(0 60% 55%)" strokeDasharray="4 3" strokeWidth={1} />
                  {isLiveEP ? (
                    <>
                      <Area type="monotone" dataKey="ep1Y" name="EP 1Y (avg $m)" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2} dot={false} />
                      {epAgg3Y.length > 2 && <Line type="monotone" dataKey="ep3Y" name="EP 3Y (rolling avg)" stroke={GOLD} strokeWidth={2} strokeDasharray="5 3" dot={false} />}
                    </>
                  ) : (
                    <>
                      <Area type="monotone" dataKey="baseline" name="Baseline EP Expectations" stroke={GOLD} fill="hsl(38 60% 52% / 0.15)" strokeWidth={2} dot={false} />
                      <Area type="monotone" dataKey="newExp" name="New EP Expectations" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2.5} dot={false} />
                    </>
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="M:B Ratio — Market Value Premium" subtitle="Market Cap / Economic Equity: captures EP expectations" live={mbByYear.length > 3}>
            {loading || mbRatio.loading ? <Skeleton h={240} /> : (() => {
              const fallback = [
                { year: "2010", median: 2.1 }, { year: "2013", median: 2.6 },
                { year: "2016", median: 3.1 }, { year: "2019", median: 3.4 },
                { year: "2022", median: 3.5 }, { year: "2024", median: 3.7 },
              ];
              const data = mbByYear.length > 3 ? mbByYear : fallback;
              // drill filter applied via mbFiltered above
              return (
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                    <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}×`} width={36} />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={1} stroke={SLATE} strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "Book Value", fill: SLATE, fontSize: 8 }} />
                    <Area type="monotone" dataKey="median" name="M:B Ratio (median)" stroke={NAVY} fill="hsl(213 75% 22% / 0.12)" strokeWidth={2} dot={{ fill: NAVY, r: 3 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              );
            })()}
          </ChartCard>
        </div>
      )}

      {/* Tab 2.2: Bow Wave Concept */}
      {tab === 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1rem" }}>
          <ChartCard title="The EP Bow Wave — Conceptual Framework" subtitle={isLiveEP ? "Live EP data showing baseline vs. new expectations curve" : "Illustrative: Market value = PV of all future EP expectations"} live={isLiveEP}>
            {loading ? <Skeleton h={300} /> : (
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={isLiveEP ? bowWaveLive : bowWaveStatic} margin={{ top: 8, right: 20, bottom: 8, left: 0 }}>
                  <defs>
                    <linearGradient id="bowFill1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={GOLD} stopOpacity={0.25}/>
                      <stop offset="95%" stopColor={GOLD} stopOpacity={0.02}/>
                    </linearGradient>
                    <linearGradient id="bowFill2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={NAVY} stopOpacity={0.2}/>
                      <stop offset="95%" stopColor={NAVY} stopOpacity={0.02}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={40} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 8 }} />
                  <ReferenceLine y={0} stroke="hsl(0 60% 55%)" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: "Zero EP", fill: "hsl(0 60% 55%)", fontSize: 8 }} />
                  {isLiveEP ? (
                    <>
                      <Area type="monotone" dataKey="ep1Y" name="EP 1Y (avg $m)" stroke={GOLD} fill="url(#bowFill1)" strokeWidth={2.5} dot={false} />
                      {epAgg3Y.length > 2 && <Area type="monotone" dataKey="ep3Y" name="EP 3Y (rolling avg)" stroke={NAVY} fill="url(#bowFill2)" strokeWidth={2} dot={false} />}
                    </>
                  ) : (
                    <>
                      <Area type="monotone" dataKey="baseline" name="Baseline EP Expectations" stroke={GOLD} fill="url(#bowFill1)" strokeWidth={2} dot={false} />
                      <Area type="monotone" dataKey="newExp" name="New EP Expectations (post-event)" stroke={NAVY} fill="url(#bowFill2)" strokeWidth={2.5} dot={false} />
                    </>
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <ChartCard title="ECF Decomposition — Dividend vs Retained" subtitle={ecfChartData.length > 0 ? "Live: Dividend ECF vs Non-Div ECF ($m)" : "Illustrative pattern"} live={ecfChartData.length > 0}>
              {loading || multiMetrics.loading ? <Skeleton h={200} /> : (() => {
                const fallback = [
                  { year: "2015", dividend: 85, retained: 95 }, { year: "2016", dividend: 90, retained: 110 },
                  { year: "2017", dividend: 98, retained: 127 }, { year: "2018", dividend: 105, retained: 140 },
                  { year: "2019", dividend: 88, retained: 127 }, { year: "2020", dividend: 72, retained: 106 },
                  { year: "2021", dividend: 95, retained: 153 }, { year: "2022", dividend: 118, retained: 167 },
                  { year: "2023", dividend: 128, retained: 184 },
                ];
                const data = ecfChartData.length > 3 ? ecfChartData : fallback;
                return (
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(210 16% 93%)" />
                      <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}m`} width={40} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                      <Area type="monotone" dataKey="retained" name="Non-Div ECF ($m)" stackId="ecf" stroke={NAVY} fill="hsl(213 75% 22% / 0.15)" strokeWidth={1.5} dot={false} />
                      <Area type="monotone" dataKey="dividend" name="Dividend ECF ($m)" stackId="ecf" stroke={GOLD} fill="hsl(38 60% 52% / 0.15)" strokeWidth={1.5} dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                );
              })()}
            </ChartCard>

            <ChartCard title="Long-Term EP Persistence" subtitle="Companies with sustained positive EP outperform — illustrative">
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={[
                  { year: "2001", sustained: 12.4, transient: 4.8, negative: -2.1 },
                  { year: "2005", sustained: 14.8, transient: 6.2, negative: -1.8 },
                  { year: "2009", sustained: 10.1, transient: 2.1, negative: -5.4 },
                  { year: "2013", sustained: 15.8, transient: 8.4, negative: -0.9 },
                  { year: "2017", sustained: 16.2, transient: 9.1, negative: -1.2 },
                  { year: "2021", sustained: 14.9, transient: 7.8, negative: -2.4 },
                  { year: "2024", sustained: 13.8, transient: 6.5, negative: -1.8 },
                ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                  <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={36} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                  <ReferenceLine y={0} stroke="hsl(0 60% 55%)" />
                  <Line type="monotone" dataKey="sustained"  name="Sustained EP+ (%TSR)" stroke={GREEN} strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="transient"  name="Transient EP+ (%TSR)" stroke={GOLD}  strokeWidth={2}   dot={false} strokeDasharray="5 3" />
                  <Line type="monotone" dataKey="negative"   name="EP− (%TSR)"           stroke="hsl(0 60% 50%)" strokeWidth={1.8} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </div>
      )}

      {/* Tab 2.3: Pair of EP Bow Waves — 1Y / 3Y / 5Y / 10Y */}
      {tab === 2 && (() => {
        // Build a paired bow-wave dataset for each interval
        // Each chart shows: old (first half of series) vs new (full series) — the classic "pair" concept
        function buildPair(agg: { year: number; value: number }[], fallbackPeak: number, fallbackShift: number) {
          if (agg.length >= 6) {
            const mid = Math.floor(agg.length / 2);
            return agg.map((d, i) => ({
              year: String(d.year),
              old:  i <= mid ? +(d.value / 1e6).toFixed(2) : null,
              live: +(d.value / 1e6).toFixed(2),
            }));
          }
          // Illustrative fallback
          return Array.from({ length: 21 }, (_, i) => ({
            year: String(2004 + i),
            old:  i <= 10 ? bell(i - 4, 2, 5, fallbackPeak) : null,
            live: bell(i - 4, 2 + fallbackShift, 6, fallbackPeak * 1.6),
          }));
        }

        const intervals: { label: string; color: string; agg: { year: number; value: number }[]; peak: number; shift: number }[] = [
          { label: "1Y",  color: NAVY,                   agg: epAgg1Y,  peak: 300, shift: 2 },
          { label: "3Y",  color: "hsl(38 60% 52%)",      agg: epAgg3Y,  peak: 280, shift: 3 },
          { label: "5Y",  color: "hsl(152 60% 40%)",     agg: epAgg5Y,  peak: 260, shift: 4 },
          { label: "10Y", color: "hsl(271 76% 53%)",     agg: epAgg10Y, peak: 220, shift: 5 },
        ];

        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {/* Header note */}
            <div style={{ gridColumn: "1/-1", padding: "0.625rem 0.875rem", borderRadius: 8, background: "hsl(213 75% 22% / 0.05)", border: "1px solid hsl(213 75% 22% / 0.12)", fontSize: "0.6875rem", color: SLATE }}>
              <b style={{ color: NAVY }}>Pair of EP Bow Waves</b> — each chart overlays the EP curve at the start of the observation period ("old expectations") against the full historical series ("new expectations"). A rising new curve signals market re-rating; a falling curve signals de-rating. Intervals: <b>1Y · 3Y · 5Y · 10Y</b> annualised EP.
            </div>

            {intervals.map(({ label, color, agg, peak, shift }) => {
              const data = buildPair(agg, peak, shift);
              const isLive = agg.length >= 6;
              return (
                <ChartCard
                  key={label}
                  title={`${label} EP Bow Wave — Pair`}
                  subtitle={isLive
                    ? `Live ${label} EP ($m avg) — old expectations vs full curve re-rating`
                    : `Illustrative ${label} annualised EP bow wave pair — run pipeline for live data`}
                  live={isLive}
                >
                  <ResponsiveContainer width="100%" height={220}>
                    <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id={`bowFillOld_${label}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={SLATE} stopOpacity={0.18} />
                          <stop offset="95%" stopColor={SLATE} stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id={`bowFillNew_${label}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={color} stopOpacity={0.22} />
                          <stop offset="95%" stopColor={color} stopOpacity={0.03} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                      <XAxis dataKey="year" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} interval={Math.floor(data.length / 6)} />
                      <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={40}
                        tickFormatter={v => isLive ? `$${v}m` : String(v)} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 9, paddingTop: 4 }} />
                      <ReferenceLine y={0} stroke="hsl(0 60% 50%)" strokeDasharray="3 2" strokeWidth={1} />
                      {/* Old curve — dashed, slate */}
                      <Area
                        type="monotone" dataKey="old"
                        name={`Old EP ${label} (prior expectation)`}
                        stroke={SLATE} fill={`url(#bowFillOld_${label})`}
                        strokeWidth={1.8} strokeDasharray="5 3" dot={false}
                        connectNulls={false}
                      />
                      {/* New / full curve — solid, colored */}
                      <Area
                        type="monotone" dataKey="live"
                        name={`New EP ${label} (re-rated curve)`}
                        stroke={color} fill={`url(#bowFillNew_${label})`}
                        strokeWidth={2.5} dot={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                  <div style={{ fontSize: "0.5625rem", color: SLATE, marginTop: 4, textAlign: "center" }}>
                    Dashed = prior EP expectations · Solid = updated full-period curve · Zero line = EP=0 (value-destructive)
                  </div>
                </ChartCard>
              );
            })}
          </div>
        );
      })()}

      {/* Tabs 2.4 & 2.5 */}
      {(tab === 3 || tab === 4) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <ChartCard title={tab === 3 ? "Long-Term Focus Proof — EP Dominant TSR" : "Reconciling Wealth Creation"} subtitle={tab === 3 ? "Companies managed for EP outperform EPS-focused peers over 10 years" : "TER-Ke reconciliation: where does shareholder wealth come from?"} live={false}>
            <ResponsiveContainer width="100%" height={230}>
              <ComposedChart data={tab === 3 ? [
                { year: "2005", epDom: 14.8, epsDom: 5.7 }, { year: "2007", epDom: 18.2, epsDom: 7.1 },
                { year: "2009", epDom: 6.2, epsDom: -4.8 }, { year: "2011", epDom: 12.4, epsDom: 4.2 },
                { year: "2013", epDom: 16.8, epsDom: 6.8 }, { year: "2015", epDom: 14.1, epsDom: 5.4 },
                { year: "2017", epDom: 17.2, epsDom: 6.9 }, { year: "2019", epDom: 12.8, epsDom: 4.8 },
                { year: "2021", epDom: 15.4, epsDom: 7.2 }, { year: "2023", epDom: 13.8, epsDom: 5.9 },
              ] : [
                { year: "2010", wc: 280, wpReq: 110, excessReturn: 170 },
                { year: "2013", wc: 350, wpReq: 130, excessReturn: 220 },
                { year: "2016", wc: 420, wpReq: 155, excessReturn: 265 },
                { year: "2019", wc: 390, wpReq: 145, excessReturn: 245 },
                { year: "2022", wc: 510, wpReq: 180, excessReturn: 330 },
                { year: "2024", wc: 560, wpReq: 195, excessReturn: 365 },
              ]} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(210 16% 92%)" />
                <XAxis dataKey="year" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={36} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                {tab === 3 ? (
                  <>
                    <Line type="monotone" dataKey="epDom"  name="EP Dominant TSR (%)"  stroke={GREEN} strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="epsDom" name="EPS Dominant TSR (%)" stroke="hsl(0 60% 50%)" strokeWidth={1.8} dot={false} strokeDasharray="5 3" />
                  </>
                ) : (
                  <>
                    <Area type="monotone" dataKey="wpReq"       name="Wealth Preservation Required" stackId="wc" stroke={SLATE} fill="hsl(215 15% 46% / 0.2)" strokeWidth={1.5} dot={false} />
                    <Area type="monotone" dataKey="excessReturn" name="Excess Return (Wealth Creation)" stackId="wc" stroke={GREEN} fill="hsl(152 60% 40% / 0.2)" strokeWidth={1.5} dot={false} />
                  </>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title={tab === 3 ? "EP vs EPS — 10yr Cumulative Outperformance" : "Wealth Creation by Sector ($B)"} subtitle={tab === 3 ? "EP-focused management outperforms by 9.1% per annum" : "Sector contribution to total ASX wealth creation"} live={false}>
            <ResponsiveContainer width="100%" height={230}>
              <ComposedChart data={tab === 3 ? [
                { label: "EP Dominant", tsr: 14.8, wealth: 185 },
                { label: "Mixed",       tsr: 9.2,  wealth: 95  },
                { label: "EPS Dominant",tsr: 5.7,  wealth: 42  },
              ] : [
                { sector: "Financials",  value: 420 }, { sector: "Materials",  value: 385 },
                { sector: "Health",      value: 210 }, { sector: "Consumer D", value: 180 },
                { sector: "Energy",      value: 145 }, { sector: "Industrials", value: 128 },
                { sector: "IT",          value: 98  }, { sector: "Utilities",  value: 72  },
              ]} margin={{ top: 4, right: 8, bottom: tab === 3 ? 0 : 16, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={tab === 4} stroke="hsl(210 16% 93%)" />
                <XAxis dataKey={tab === 3 ? "label" : "sector"} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => `${tab === 3 ? v + "%" : "$" + v + "B"}`} width={40} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 9, paddingTop: 6 }} />
                {tab === 3 ? (
                  <>
                    <Bar dataKey="tsr"    name="10yr Ann. TSR (%)"   fill={NAVY}  radius={[4, 4, 0, 0]} maxBarSize={40} />
                    <Bar dataKey="wealth" name="Wealth Created ($B)" fill={GOLD}  radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </>
                ) : (
                  <Bar dataKey="value" name="Wealth Creation ($B)" fill={NAVY} radius={[4, 4, 0, 0]} maxBarSize={28} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      <style>{`
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
      `}</style>
    </div>
  );
}
