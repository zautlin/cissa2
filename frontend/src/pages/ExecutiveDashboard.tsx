/**
 * Executive Dashboard — CISSA Financial Platform
 * Logical flow: Market Context → Wealth Creation → EP Bow Wave → Valuation → Cost Structure
 * Highlights: Beta, TSR, EE, ECF, Ke, M:B — live data from API
 */
import { useState } from "react";
import {
  ComposedChart, AreaChart, BarChart, LineChart, ScatterChart,
  Area, Bar, Line, Scatter, XAxis, YAxis, ZAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine, Cell, RadarChart, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { useDrillDown, DrillDownBanner } from "../context/DrillDown";
import { useActiveContext, useMultipleMetrics, useRatioMetric, aggregateByYear } from "../hooks/useMetrics";

// ─── Design tokens ────────────────────────────────────────────────────────────
const NAV   = "#0E2D5C";
const GOLD  = "#C8922A";
const GREEN = "#2E9B65";
const RED   = "#D94F4F";
const SLATE = "#6B7894";
const TEAL  = "#0891b2";
const PURPLE= "#7c3aed";
const LIGHT = "#F4F7FE";

// ─── Dummy Data ───────────────────────────────────────────────────────────────


// EP Bow Wave — multiple T0 years (like the Excel charts)
const BOW_WAVE_YEARS = ["2015","2016","2017","2018","2019","2020"];
const BOW_WAVE_COLORS = [NAV, GOLD, GREEN, RED, TEAL, PURPLE];
const T_LABELS = ["T-10","T-8","T-6","T-4","T-2","T0","T2","T4","T6","T8","T10"];
function gaussianBowWave(peak: number, shift: number) {
  return T_LABELS.map((t, i) => {
    const x = i - 5 - shift;
    const v = peak * Math.exp(-(x*x) / 8);
    return +(v).toFixed(0);
  });
}
const bowWaveData = T_LABELS.map((t, i) => {
  const row: any = { t };
  BOW_WAVE_YEARS.forEach((yr, j) => {
    const wave = gaussianBowWave([800, 600, 1100, 400, 700, 950][j], j - 3);
    row[yr] = wave[i];
  });
  return row;
});

// EP% Delivered vs Expected
const EP_DEL_EXP = [
  { sector:"Materials",   delivered: 14.2, expected: 12.1, eeai: 117 },
  { sector:"Financials",  delivered: 11.8, expected: 13.2, eeai: 89  },
  { sector:"Energy",      delivered: 9.1,  expected: 10.5, eeai: 87  },
  { sector:"Health Care", delivered: 18.5, expected: 15.2, eeai: 122 },
  { sector:"Industrials", delivered: 7.4,  expected: 8.9,  eeai: 83  },
  { sector:"Technology",  delivered: 22.1, expected: 18.3, eeai: 121 },
  { sector:"Consumer",    delivered: 8.9,  expected: 9.2,  eeai: 97  },
  { sector:"Utilities",   delivered: 6.1,  expected: 7.8,  eeai: 78  },
];

// EEAI Heatmap — companies × years (subset)
const EEAI_COMPANIES = ["BHP","CBA","WBC","CSL","NAB","ANZ","RIO","WES","TLS","TCL"];
const EEAI_YEARS = ["2018","2019","2020","2021","2022","2023","2024"];
const EEAI_DATA = EEAI_COMPANIES.map(co => {
  const row: any = { company: co };
  EEAI_YEARS.forEach(yr => {
    row[yr] = Math.floor(60 + Math.random() * 140);
  });
  return row;
});


// Wealth creation bridge (waterfall-style)
const WEALTH_BRIDGE = [
  { label:"FV ECF",    value: 2571, color: GREEN },
  { label:"Δ Equity",  value: 1610, color: NAV  },
  { label:"TER Alpha", value: 413,  color: GOLD  },
  { label:"Mkt Mvmt",  value: -180, color: RED   },
  { label:"Total",     value: 4414, color: TEAL  },
];

// Cost structure waterfall
const COST_WATERFALL = [
  { label:"Revenue",  value: 100, color: NAV  },
  { label:"Op Cost",  value: -62, color: GOLD },
  { label:"Non-Op",   value: -8,  color: SLATE },
  { label:"Tax",      value: -7,  color: RED  },
  { label:"XO Cost",  value: -3,  color: PURPLE },
  { label:"EP Margin",value: 20,  color: GREEN },
];

// MB Ratio trend
const MB_RATIO = [
  { year:"2010", mb:2.1 }, { year:"2012", mb:2.4 }, { year:"2014", mb:2.8 },
  { year:"2016", mb:3.1 }, { year:"2018", mb:3.4 }, { year:"2020", mb:2.9 },
  { year:"2022", mb:3.5 }, { year:"2024", mb:3.7 },
];


// Radar: top company profile
const RADAR_DATA = [
  { metric:"EP%",    BHP:72, CBA:85 },
  { metric:"ROEE",   BHP:65, CBA:90 },
  { metric:"M:B",    BHP:55, CBA:80 },
  { metric:"TSR",    BHP:70, CBA:75 },
  { metric:"TER α",  BHP:60, CBA:70 },
  { metric:"EE Grth",BHP:68, CBA:62 },
];

// ─── Components ───────────────────────────────────────────────────────────────

const TT = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:"#fff", border:"1px solid #e2e8f0", borderRadius:8, padding:"8px 12px", boxShadow:"0 4px 16px rgba(0,0,0,0.10)", fontSize:12 }}>
      <div style={{ fontWeight:700, color:"hsl(220 35% 18%)", marginBottom:4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color:p.color, display:"flex", gap:6, alignItems:"center", marginBottom:2 }}>
          <div style={{ width:8,height:8,borderRadius:"50%",background:p.color,flexShrink:0 }} />
          <span>{p.name}: <b>{typeof p.value==="number" ? p.value.toFixed(1) : p.value}</b></span>
        </div>
      ))}
    </div>
  );
};

function Card({ title, subtitle, badge, children, span = 1 }: {
  title: string; subtitle?: string; badge?: string; children: React.ReactNode; span?: number;
}) {
  return (
    <div style={{
      background:"#fff", borderRadius:12, border:"1px solid #e2e8f0",
      padding:"16px 20px", boxShadow:"0 1px 4px rgba(14,45,92,0.06)",
      gridColumn: span > 1 ? `span ${span}` : undefined,
    }}>
      <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:12 }}>
        <div>
          <div style={{ fontSize:13, fontWeight:700, color:NAV }}>{title}</div>
          {subtitle && <div style={{ fontSize:11, color:SLATE, marginTop:2 }}>{subtitle}</div>}
        </div>
        {badge && (
          <span style={{
            fontSize:9, fontWeight:800, padding:"2px 7px", borderRadius:999,
            background:"hsl(38 60% 52% / 0.12)", color:"hsl(38 60% 30%)",
            border:"1px solid hsl(38 60% 52% / 0.25)", textTransform:"uppercase",
          }}>{badge}</span>
        )}
      </div>
      {children}
    </div>
  );
}

function KPICard({ label, value, sub, color, delta }: {
  label: string; value: string; sub?: string; color?: string; delta?: string;
}) {
  const up = delta && !delta.startsWith("-");
  return (
    <div style={{
      background:"#fff", borderRadius:12, border:"1px solid #e2e8f0",
      padding:"16px 20px", boxShadow:"0 1px 4px rgba(14,45,92,0.06)",
    }}>
      <div style={{ fontSize:11, color:SLATE, fontWeight:600, textTransform:"uppercase", letterSpacing:0.5, marginBottom:4 }}>{label}</div>
      <div style={{ fontSize:26, fontWeight:800, color:color||NAV, lineHeight:1.1 }}>{value}</div>
      {sub && <div style={{ fontSize:11, color:SLATE, marginTop:2 }}>{sub}</div>}
      {delta && (
        <div style={{ fontSize:11, fontWeight:700, color:up?GREEN:RED, marginTop:4, display:"flex", alignItems:"center", gap:3 }}>
          <span>{up?"▲":"▼"}</span>{delta} vs prior year
        </div>
      )}
    </div>
  );
}

function SectionHeader({ n, title, sub }: { n: string; title: string; sub: string }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:12, margin:"28px 0 12px", gridColumn:"1/-1" }}>
      <div style={{ width:36, height:36, borderRadius:"50%", background:NAV, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
        <span style={{ fontSize:14, fontWeight:800, color:"#fff" }}>{n}</span>
      </div>
      <div>
        <div style={{ fontSize:16, fontWeight:800, color:NAV }}>{title}</div>
        <div style={{ fontSize:11, color:SLATE }}>{sub}</div>
      </div>
    </div>
  );
}

// ─── EEAI Heatmap cell ────────────────────────────────────────────────────────
function HeatCell({ v, onDrill, ticker }: { v: number; onDrill: (t: string) => void; ticker: string }) {
  const pct = Math.min(Math.max((v - 60) / 140, 0), 1);
  const bg = v >= 100
    ? `hsl(213 75% ${Math.round(22 + (1 - pct) * 40)}%)`
    : `hsl(0 60% ${Math.round(48 + (1 - pct) * 20)}%)`;
  return (
    <td
      onClick={() => onDrill(ticker)}
      title={`EEAI: ${v}`}
      style={{
        background:bg, color:"#fff", fontSize:9, fontWeight:700,
        textAlign:"center", padding:"4px 2px", cursor:"pointer",
        border:"1px solid rgba(255,255,255,0.15)",
        transition:"opacity 0.12s",
      }}
    >{v}</td>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function ExecutiveDashboard() {
  const drill = useDrillDown();
  const [bowYear, setBowYear] = useState<string | null>(null);

  // ─── Live data ─────────────────────────────────────────────────────────────
  const ctx = useActiveContext();
  const coreMetrics = useMultipleMetrics(ctx.datasetId, ctx.paramSetId, [
    "Calc Beta", "Calc Ke", "Calc Rf", "Calc ECF", "Calc FY TSR", "Calc EE",
    "Calc 1Y FV ECF", "Calc 3Y FV ECF", "Calc 5Y FV ECF", "Calc 10Y FV ECF",
    "Calc 1Y TER", "Calc EP",
  ]);
  const mbData        = useRatioMetric(ctx.datasetId, ctx.paramSetId, "mb_ratio");
  const opCostData    = useRatioMetric(ctx.datasetId, ctx.paramSetId, "op_cost_margin",    "1Y");
  const nonOpCostData = useRatioMetric(ctx.datasetId, ctx.paramSetId, "non_op_cost_margin", "1Y");
  const xoCostData    = useRatioMetric(ctx.datasetId, ctx.paramSetId, "xo_cost_margin",     "1Y");
  const profitData    = useRatioMetric(ctx.datasetId, ctx.paramSetId, "profit_margin",       "1Y");

  // ─── KPI computed values ───────────────────────────────────────────────────
  const keByYear   = aggregateByYear(coreMetrics.data["Calc Ke"]     ?? []);
  const betaByYear = aggregateByYear(coreMetrics.data["Calc Beta"]   ?? []);
  const tsrByYear  = aggregateByYear(coreMetrics.data["Calc FY TSR"] ?? []);
  const ecfByYear  = aggregateByYear(coreMetrics.data["Calc ECF"]    ?? []);
  const eeByYear   = aggregateByYear(coreMetrics.data["Calc EE"]     ?? []);

  const latestKe   = keByYear.length   ? keByYear[keByYear.length - 1].value     : null;
  const prevKe     = keByYear.length   > 1 ? keByYear[keByYear.length - 2].value : null;
  const latestBeta = betaByYear.length ? betaByYear[betaByYear.length - 1].value : null;
  const prevBeta   = betaByYear.length > 1 ? betaByYear[betaByYear.length - 2].value : null;
  const latestTSR  = tsrByYear.length  ? tsrByYear[tsrByYear.length - 1].value   : null;
  const prevTSR    = tsrByYear.length  > 1 ? tsrByYear[tsrByYear.length - 2].value : null;
  const latestECF  = ecfByYear.length  ? ecfByYear[ecfByYear.length - 1].value   : null;
  const prevECF    = ecfByYear.length  > 1 ? ecfByYear[ecfByYear.length - 2].value : null;
  const latestEE   = eeByYear.length   ? eeByYear[eeByYear.length - 1].value     : null;
  const prevEE     = eeByYear.length   > 1 ? eeByYear[eeByYear.length - 2].value : null;

  const mbVals   = mbData.data.filter(r => r.value !== null);
  const latestMB = mbVals.length
    ? mbVals.reduce((s, r) => s + (r.value as number), 0) / mbVals.length
    : null;

  // ─── Section 4: TER/TSR/Ke + Ke Decomposition ────────────────────────────
  const rfByYear  = aggregateByYear(coreMetrics.data["Calc Rf"]     ?? []);
  const terByYear = aggregateByYear(coreMetrics.data["Calc 1Y TER"] ?? []);

  interface TerTsrPoint { year: string; tsr: number | null; ter: number | null; ke: number | null; }
  const terTsrChart: TerTsrPoint[] = tsrByYear.map(d => ({
    year: String(d.year),
    tsr: d.value !== null ? +(d.value * 100).toFixed(1) : null,
    ter: +((terByYear.find(x => x.year === d.year)?.value ?? 0) * 100).toFixed(1),
    ke:  +((keByYear.find(x => x.year === d.year)?.value  ?? 0) * 100).toFixed(1),
  })).slice(-15);

  interface KeDecompPoint { year: string; rf: number | null; erp: number | null; }
  const keDecompChart: KeDecompPoint[] = keByYear.map(d => {
    const rf  = rfByYear.find(x => x.year === d.year)?.value ?? null;
    const erp = d.value !== null && rf !== null ? d.value - rf : null;
    return {
      year: String(d.year),
      rf:  rf  !== null ? +(rf  * 100).toFixed(1) : null,
      erp: erp !== null ? +(erp * 100).toFixed(1) : null,
    };
  }).slice(-15);

  // ─── Section 3: FV-ECF bar chart data structure ───────────────────────────
  const fv1yByYear  = aggregateByYear(coreMetrics.data["Calc 1Y FV ECF"]  ?? []);
  const fv3yByYear  = aggregateByYear(coreMetrics.data["Calc 3Y FV ECF"]  ?? []);
  const fv5yByYear  = aggregateByYear(coreMetrics.data["Calc 5Y FV ECF"]  ?? []);
  const fv10yByYear = aggregateByYear(coreMetrics.data["Calc 10Y FV ECF"] ?? []);

  interface FvEcfPoint { interval: string; fv: number | null; }
  const fvEcfChart: FvEcfPoint[] = [
    { interval: "1Y",  fv: fv1yByYear.length  ? +(( fv1yByYear[fv1yByYear.length - 1].value   ?? 0) / 1e9).toFixed(1) : null },
    { interval: "3Y",  fv: fv3yByYear.length  ? +(( fv3yByYear[fv3yByYear.length - 1].value   ?? 0) / 1e9).toFixed(1) : null },
    { interval: "5Y",  fv: fv5yByYear.length  ? +(( fv5yByYear[fv5yByYear.length - 1].value   ?? 0) / 1e9).toFixed(1) : null },
    { interval: "10Y", fv: fv10yByYear.length ? +((fv10yByYear[fv10yByYear.length - 1].value  ?? 0) / 1e9).toFixed(1) : null },
  ];

  // ─── Section 5: M:B Ratio trend (live from ratio-metrics) ───────────────
  interface MbPoint { year: string; mb: number | null; }
  const mbTrendData: MbPoint[] = (() => {
    const byYear: Record<number, number[]> = {};
    (mbData.data ?? []).forEach(item => {
      (item.time_series ?? []).forEach(ts => {
        if (ts.value !== null) {
          if (!byYear[ts.year]) byYear[ts.year] = [];
          byYear[ts.year].push(ts.value);
        }
      });
    });
    return Object.entries(byYear)
      .map(([y, vals]) => ({ year: String(y), mb: +(vals.reduce((s, v) => s + v, 0) / vals.length).toFixed(2) }))
      .sort((a, b) => Number(a.year) - Number(b.year))
      .slice(-15);
  })();

  // ─── Section 9: Cost Structure Waterfall (live from ratio-metrics) ─────────
  interface WaterfallBar { label: string; value: number; color: string; }
  const costWaterfallData: WaterfallBar[] | null = (() => {
    const med = (items: typeof opCostData.data) => {
      const vals = items.filter(r => r.value !== null).map(r => r.value as number * 100).sort((a, b) => a - b);
      return vals.length ? vals[Math.floor(vals.length / 2)] : null;
    };
    const opCost    = med(opCostData.data);
    const nonOpCost = med(nonOpCostData.data);
    const xoCost    = med(xoCostData.data);
    const profit    = med(profitData.data);
    if (opCost === null && profit === null) return null;
    return [
      { label: "Revenue",   value: 100,                                                color: NAV    },
      { label: "Op Cost",   value: opCost    !== null ? -Math.abs(+opCost.toFixed(1))    : 0, color: GOLD   },
      { label: "Non-Op",    value: nonOpCost !== null ? -Math.abs(+nonOpCost.toFixed(1)) : 0, color: SLATE  },
      { label: "XO Cost",   value: xoCost    !== null ? -Math.abs(+xoCost.toFixed(1))    : 0, color: PURPLE },
      { label: "EP Margin", value: profit    !== null ? +profit.toFixed(1)                : 0, color: GREEN  },
    ];
  })();

  // ─── Section 6: Sector Aggregations (live) ──────────────────────────────
  interface SectorRow {
    sector: string;
    epDelivered: number | null;
    epExpected:  number | null;
    eeai:        number | null;
    mb:          number | null;
    tsr:         number | null;
    ke:          number | null;
    eeGrowth:    number | null;
    epTrend:     "positive" | "declining" | null;
  }
  const sectorAggRows: SectorRow[] | null = (() => {
    if (!mbData.data.length) return null;

    // Ticker → sector from enriched mbData
    const tickerSector = new Map<string, string>();
    mbData.data.forEach(r => tickerSector.set(r.ticker, r.sector));

    // Per-ticker latest non-null value from MetricResultItem[]
    const latestMap = (data: { ticker: string; fiscal_year: number; value: number | null }[]): Map<string, number> => {
      const m = new Map<string, { year: number; val: number }>();
      data.forEach(r => {
        if (r.value !== null) {
          const e = m.get(r.ticker);
          if (!e || r.fiscal_year > e.year) m.set(r.ticker, { year: r.fiscal_year, val: r.value });
        }
      });
      const out = new Map<string, number>();
      m.forEach(({ val }, k) => out.set(k, val));
      return out;
    };

    const median = (vals: number[]): number | null => {
      if (!vals.length) return null;
      const s = [...vals].sort((a, b) => a - b);
      return s[Math.floor(s.length / 2)];
    };

    const epLatest  = latestMap(coreMetrics.data["Calc EP"]     ?? []);
    const eeLatest  = latestMap(coreMetrics.data["Calc EE"]     ?? []);
    const keLatest  = latestMap(coreMetrics.data["Calc Ke"]     ?? []);
    const tsrLatest = latestMap(coreMetrics.data["Calc FY TSR"] ?? []);
    const mbLatest  = new Map<string, number>();
    mbData.data.forEach(r => { if (r.value !== null) mbLatest.set(r.ticker, r.value as number); });

    // EE YoY growth per ticker
    const eeGrowthMap = (() => {
      const byTicker: Record<string, { year: number; val: number }[]> = {};
      (coreMetrics.data["Calc EE"] ?? []).forEach(r => {
        if (r.value !== null) {
          if (!byTicker[r.ticker]) byTicker[r.ticker] = [];
          byTicker[r.ticker].push({ year: r.fiscal_year, val: r.value });
        }
      });
      const m = new Map<string, number>();
      Object.entries(byTicker).forEach(([ticker, series]) => {
        series.sort((a, b) => a.year - b.year);
        if (series.length >= 2) {
          const prev = series[series.length - 2].val;
          const curr = series[series.length - 1].val;
          if (prev !== 0) m.set(ticker, (curr - prev) / Math.abs(prev) * 100);
        }
      });
      return m;
    })();

    // Group tickers by sector
    const sectorTickers: Record<string, string[]> = {};
    tickerSector.forEach((sector, ticker) => {
      if (!sectorTickers[sector]) sectorTickers[sector] = [];
      sectorTickers[sector].push(ticker);
    });

    const collect = (m: Map<string, number>, tickers: string[]) =>
      tickers.flatMap(t => { const v = m.get(t); return v !== undefined ? [v] : []; });

    const rows = Object.entries(sectorTickers).map(([sector, tickers]) => {
      const keVals  = collect(keLatest, tickers);
      const tsrVals = collect(tsrLatest, tickers);
      const mbValsS = collect(mbLatest, tickers);
      const eeGVals = collect(eeGrowthMap, tickers);
      const epVals  = collect(epLatest, tickers);

      // EP% = EP / EE per ticker, then sector median
      const epPctVals = tickers.flatMap(t => {
        const ep = epLatest.get(t); const ee = eeLatest.get(t);
        return ep !== undefined && ee !== undefined && ee !== 0 ? [ep / ee * 100] : [];
      });

      const keMedian = median(keVals);
      const epPct    = median(epPctVals);
      // EEAI = (EP/EE) / Ke * 100 — 100 = exactly meeting cost of equity
      const eeai = epPct !== null && keMedian !== null && keMedian !== 0
        ? Math.round(epPct / (keMedian * 100) * 100) : null;
      const epMedian = median(epVals);

      return {
        sector,
        epDelivered: epPct    !== null ? +epPct.toFixed(1)            : null,
        epExpected:  keMedian !== null ? +(keMedian * 100).toFixed(1)  : null,
        eeai,
        mb:          median(mbValsS),
        tsr:         median(tsrVals) !== null ? +(median(tsrVals)! * 100).toFixed(1) : null,
        ke:          keMedian !== null ? +(keMedian * 100).toFixed(1) : null,
        eeGrowth:    median(eeGVals) !== null ? +median(eeGVals)!.toFixed(1) : null,
        epTrend:     epMedian !== null ? (epMedian > 0 ? "positive" : "declining") as "positive" | "declining" : null,
      } as SectorRow;
    });

    return rows.length ? rows.sort((a, b) => a.sector.localeCompare(b.sector)) : null;
  })();

  // ─── Section 2: trend chart data structure ────────────────────────────────
  interface TrendPoint { year: string; ee: number | null; ecf: number | null; tsr: number | null; }
  const trendChart: TrendPoint[] = eeByYear.map(d => ({
    year: String(d.year),
    ee:  d.value,
    ecf: ecfByYear.find(x => x.year === d.year)?.value ?? null,
    tsr: tsrByYear.find(x => x.year === d.year)?.value ?? null,
  })).slice(-15);

  // ─── Formatters ────────────────────────────────────────────────────────────
  const fmtPct   = (v: number | null, d = 1) => v !== null ? `${v.toFixed(d)}%` : "—";
  const fmtVal   = (v: number | null, d = 2) => v !== null ? v.toFixed(d) : "—";
  const fmtX     = (v: number | null, d = 2) => v !== null ? `${v.toFixed(d)}×` : "—";
  const fmtDelta = (curr: number | null, prev: number | null, suffix = "%") => {
    if (curr === null || prev === null) return undefined;
    const d = curr - prev;
    return `${d >= 0 ? "+" : ""}${d.toFixed(1)}${suffix}`;
  };

  // ─── Loading / no-data guards ──────────────────────────────────────────────
  if (ctx.loading || coreMetrics.loading || mbData.loading) {
    return (
      <div style={{ padding: 48, textAlign: "center", color: SLATE, fontSize: 14 }}>
        Loading metrics…
      </div>
    );
  }
  if (!ctx.hasMetrics) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: NAV, marginBottom: 8 }}>
          No data available
        </div>
        <div style={{ color: SLATE, fontSize: 13, marginBottom: 16 }}>
          Run the ETL pipeline first to populate metrics.
        </div>
        <a href="#/pipeline" style={{ color: TEAL, fontWeight: 600, fontSize: 13 }}>
          Go to Pipeline →
        </a>
      </div>
    );
  }

  return (
    <div style={{ padding:"28px 32px", background:LIGHT, minHeight:"100vh" }}>
      <DrillDownBanner />

      {/* ── Page Title ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom:24 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:4, height:40, borderRadius:2, background:GOLD }} />
          <div>
            <h1 style={{ fontSize:22, fontWeight:800, color:NAV, margin:0 }}>
              Executive Dashboard
            </h1>
            <p style={{ color:SLATE, fontSize:13, margin:"4px 0 0" }}>
              Capital Intelligence · Shareholder Alignment · Wealth Creation Overview
            </p>
          </div>
        </div>
      </div>

      {/* ── Section 1: Market Context KPIs ─────────────────────────────── */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:16, marginBottom:8 }}>
        <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:10, marginBottom:4 }}>
          <div style={{ width:3, height:20, background:NAV, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§1 Market Context</span>
          <span style={{ fontSize:11, color:SLATE }}>— Market Cap · TSR · Economic Equity · ECF</span>
        </div>
        <KPICard label="Avg Beta" value={fmtVal(latestBeta)} sub="Median market beta" delta={fmtDelta(latestBeta, prevBeta, "")} color={NAV} />
        <KPICard label="TSR 1Y" value={fmtPct(latestTSR)} sub="Total Shareholder Return" delta={fmtDelta(latestTSR, prevTSR)} color={GREEN} />
        <KPICard label="Econ. Equity (EE)" value={fmtVal(latestEE, 0)} sub="Median Economic Equity" delta={fmtDelta(latestEE, prevEE, "")} color={TEAL} />
        <KPICard label="Equity Cash Flow (ECF)" value={fmtVal(latestECF, 0)} sub="Median ECF" delta={fmtDelta(latestECF, prevECF, "")} color={GOLD} />
        <KPICard label="Cost of Equity (Ke)" value={fmtPct(latestKe)} sub="CAPM: Rf + β×ERP" delta={fmtDelta(latestKe, prevKe)} color={SLATE} />
        <KPICard label="M:B Ratio" value={fmtX(latestMB)} sub="Market Cap / Econ. Equity" color={PURPLE} />
      </div>

      {/* ── MC + TSR + EE + ECF chart ─────────────────────────────────── */}
      <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:16, marginBottom:16 }}>
        <Card title="EE, ECF & TSR — Year-on-Year Trend" subtitle="EE (area, left axis) · ECF & TSR (lines, right axis)">
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={trendChart} margin={{ top:4, right:8, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="year" tick={{ fontSize:9 }} tickLine={false} axisLine={false} />
              <YAxis yAxisId="left" tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={44} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={36} tickFormatter={(v: number) => v.toFixed(1)} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize:9, paddingTop:6 }} />
              <Area yAxisId="left" type="monotone" dataKey="ee" name="Econ. Equity" stroke={TEAL} fill={`${TEAL}18`} strokeWidth={2} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="ecf" name="ECF" stroke={GOLD} strokeWidth={2.5} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="tsr" name="TSR (%)" stroke={GREEN} strokeWidth={2} strokeDasharray="5 3" dot={false} />
              <ReferenceLine yAxisId="right" y={0} stroke={RED} strokeDasharray="3 2" strokeWidth={1} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="FV-ECF Valuation Intervals" subtitle="Future value of ECF at 1Y/3Y/5Y/10Y horizons (A$B)">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={fvEcfChart} margin={{ top:4, right:4, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef0f5" />
              <XAxis dataKey="interval" tick={{ fontSize:10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={40} tickFormatter={v=>`$${v}B`} />
              <Tooltip content={<TT />} />
              <Bar dataKey="fv" name="FV-ECF ($B)" radius={[6,6,0,0]}
                label={{ position:"top", fontSize:9, formatter:(v: number)=>`$${v}B` }}>
                {fvEcfChart.map((_, i) => <Cell key={i} fill={[NAV,TEAL,GREEN,GOLD][i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Section 2: EP Bow Wave ──────────────────────────────────────── */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:16, marginBottom:16 }}>
        <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:3, height:20, background:GOLD, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§2 EP Bow Wave</span>
          <span style={{ fontSize:11, color:SLATE }}>— Multiple T0 years · economic profit trajectory</span>
        </div>

        <Card title="EP Bow Wave — Multiple T0 Years" subtitle="Economic Profit ($m) for each T0 year — past actual, future projected" span={2}>
          {/* T0 year selector */}
          <div style={{ display:"flex", gap:6, flexWrap:"wrap", marginBottom:12 }}>
            <button onClick={() => setBowYear(null)} style={{ padding:"4px 12px", borderRadius:6, border:"1px solid #e2e8f0", background:!bowYear?NAV:"transparent", color:!bowYear?"#fff":SLATE, fontSize:10, fontWeight:700, cursor:"pointer" }}>All Years</button>
            {BOW_WAVE_YEARS.map((yr, i) => (
              <button key={yr} onClick={() => setBowYear(yr === bowYear ? null : yr)} style={{
                padding:"4px 12px", borderRadius:6, border:`1px solid ${BOW_WAVE_COLORS[i]}44`,
                background:bowYear===yr?BOW_WAVE_COLORS[i]:`${BOW_WAVE_COLORS[i]}12`,
                color:bowYear===yr?"#fff":BOW_WAVE_COLORS[i], fontSize:10, fontWeight:700, cursor:"pointer",
              }}>T₀={yr}</button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={bowWaveData} margin={{ top:4, right:8, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="t" tick={{ fontSize:9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={44} tickFormatter={v=>`$${v}`} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize:9, paddingTop:6 }} />
              <ReferenceLine y={0} stroke={RED} strokeDasharray="4 3" strokeWidth={1} label={{ value:"EP=0", fill:RED, fontSize:8 }} />
              <ReferenceLine x="T0" stroke={SLATE} strokeDasharray="6 3" strokeWidth={1.5} label={{ value:"T₀", fill:SLATE, fontSize:9 }} />
              {BOW_WAVE_YEARS.map((yr, i) => (
                (!bowYear || bowYear === yr) ? (
                  <Line key={yr} type="monotone" dataKey={yr} name={`EP T₀=${yr}`}
                    stroke={BOW_WAVE_COLORS[i]} strokeWidth={bowYear===yr?3:1.5}
                    dot={false} opacity={bowYear && bowYear!==yr?0.2:1} />
                ) : null
              ))}
            </ComposedChart>
          </ResponsiveContainer>
          <div style={{ fontSize:10, color:SLATE, marginTop:6, textAlign:"center" }}>
            T-10 = 10 years before measurement · T0 = measurement date · T+10 = 10 years projected forward · Bow wave shows market-embedded EP expectations
          </div>
        </Card>
      </div>

      {/* ── Section 3: EP Delivered vs Expected + EEAI ──────────────────── */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
        <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:3, height:20, background:GREEN, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§3 EP Delivered vs Expected · EEAI</span>
        </div>

        <Card title="EP% Delivered vs Expected by Sector" subtitle="Delivered = actual EP%; Expected = market-embedded rate. EEAI = Delivered/Expected × 100">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={EP_DEL_EXP} margin={{ top:4, right:8, bottom:0, left:0 }}
              onClick={(d) => { if (d?.activePayload?.[0]?.payload?.sector) drill.drillIntoSector(d.activePayload[0].payload.sector); }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef0f5" />
              <XAxis dataKey="sector" tick={{ fontSize:8 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={32} tickFormatter={v=>`${v}%`} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize:9, paddingTop:6 }} />
              <Bar dataKey="delivered" name="EP% Delivered" fill={GREEN} radius={[3,3,0,0]} maxBarSize={18} cursor="pointer" />
              <Bar dataKey="expected"  name="EP% Expected"  fill={GOLD}  radius={[3,3,0,0]} maxBarSize={18} cursor="pointer" />
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize:9, color:SLATE, marginTop:6 }}>▶ Click a sector bar to drill-down all charts</div>
        </Card>

        <Card title="EEAI Heatmap — Company × Year" subtitle="Empirical EP Alignment Index. Blue = over-delivering (≥100), Red = under-delivering (<100)">
          <div style={{ overflowX:"auto" }}>
            <table style={{ borderCollapse:"collapse", width:"100%", fontSize:9 }}>
              <thead>
                <tr>
                  <th style={{ padding:"3px 6px", textAlign:"left", fontSize:9, color:SLATE, fontWeight:700, background:LIGHT }}>Company</th>
                  {EEAI_YEARS.map(yr => (
                    <th key={yr} style={{ padding:"3px 4px", textAlign:"center", fontSize:9, color:SLATE, fontWeight:700, background:LIGHT, minWidth:36 }}>{yr}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {EEAI_DATA.map(row => (
                  <tr key={row.company}>
                    <td
                      style={{ padding:"3px 6px", fontSize:9, fontWeight:700, color:NAV, cursor:"pointer", whiteSpace:"nowrap" }}
                      onClick={() => drill.drillIntoTicker(row.company)}
                    >{row.company}</td>
                    {EEAI_YEARS.map(yr => (
                      <HeatCell key={yr} v={row[yr]} onDrill={drill.drillIntoTicker} ticker={row.company} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize:9, color:SLATE, marginTop:6 }}>▶ Click company name or cell to drill into that ticker</div>
        </Card>
      </div>

      {/* ── Section 4: TER/TSR + Ke Decomp ─────────────────────────────── */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16, marginBottom:16 }}>
        <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:3, height:20, background:TEAL, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§4 Capital Returns · Cost of Capital</span>
        </div>

        <Card title="TER vs TSR vs Ke" subtitle="Total Equity Return · Shareholder Return · Cost of Equity hurdle (%)" span={2}>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={terTsrChart} margin={{ top:4, right:8, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="year" tick={{ fontSize:9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={36} tickFormatter={v=>`${v}%`} />
              <Tooltip content={<TT />} />
              <Legend wrapperStyle={{ fontSize:9, paddingTop:6 }} />
              <ReferenceLine y={0} stroke={RED} strokeDasharray="3 2" />
              <Bar dataKey="tsr" name="TSR (%)" fill={`${NAV}22`} stroke={NAV} strokeWidth={1} maxBarSize={18} radius={[3,3,0,0]}/>
              <Line type="monotone" dataKey="ter" name="TER (%)" stroke={GREEN} strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="ke"  name="Ke (%)"  stroke={GOLD}  strokeWidth={2} strokeDasharray="5 3" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Ke Decomposition" subtitle="CAPM: Rf (risk-free) + β×ERP (equity risk premium) → Ke">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={keDecompChart} margin={{ top:4, right:4, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="year" tick={{ fontSize:8 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:8 }} tickLine={false} axisLine={false} width={32} tickFormatter={v=>`${v}%`} />
              <Tooltip content={<TT />} />
              <Bar dataKey="rf"  name="Rf" stackId="ke" fill={TEAL} radius={[0,0,0,0]} maxBarSize={22} />
              <Bar dataKey="erp" name="β×ERP" stackId="ke" fill={GOLD} radius={[3,3,0,0]} maxBarSize={22} />
              <Line type="monotone" dataKey="ke" name="Ke" stroke={NAV} strokeWidth={2.5} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Section 5: Wealth Creation + M:B + Cost Structure + Radar ──── */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16, marginBottom:16 }}>
        <div style={{ gridColumn:"1/-1", display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:3, height:20, background:PURPLE, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§5 Wealth Creation · Valuation · Fundamentals</span>
        </div>

        <Card title="Wealth Creation Sources" subtitle="Decomposition: FV-ECF + ΔEquity + TER Alpha + Mkt Movements">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={WEALTH_BRIDGE} layout="vertical" margin={{ top:4, right:40, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#eef0f5" />
              <XAxis type="number" tick={{ fontSize:8 }} tickLine={false} axisLine={false} tickFormatter={v=>`$${v}`} />
              <YAxis type="category" dataKey="label" tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={64} />
              <Tooltip content={<TT />} />
              <Bar dataKey="value" name="Value ($B)" radius={[0,4,4,0]} maxBarSize={18}
                label={{ position:"right", fontSize:9, formatter:(v:number)=>`$${v}B` }}>
                {WEALTH_BRIDGE.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="M:B Ratio Trend" subtitle="Market Cap / Economic Equity — a premium above 1× = wealth creation" badge={mbTrendData.length > 0 ? "● LIVE" : "ILLUS."}>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={mbTrendData.length > 0 ? mbTrendData : MB_RATIO} margin={{ top:4, right:4, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f5" />
              <XAxis dataKey="year" tick={{ fontSize:9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:9 }} tickLine={false} axisLine={false} width={28} tickFormatter={v=>`${v}×`} />
              <Tooltip content={<TT />} />
              <ReferenceLine y={1} stroke={RED} strokeDasharray="4 3" label={{ value:"Book=1×", fill:RED, fontSize:8 }} />
              <Area type="monotone" dataKey="mb" name="M:B Ratio" stroke={NAV} fill={`${NAV}12`} strokeWidth={2.5} dot={{ r:3, fill:NAV }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Cost Structure Waterfall" subtitle="Revenue → EP Margin decomposition — cross-sectional median (% of revenue)" badge={costWaterfallData ? "● LIVE" : "ILLUS."}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={costWaterfallData ?? COST_WATERFALL} margin={{ top:4, right:8, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef0f5" />
              <XAxis dataKey="label" tick={{ fontSize:8 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize:8 }} tickLine={false} axisLine={false} width={28} tickFormatter={v=>`${v}%`} />
              <Tooltip content={<TT />} />
              <Bar dataKey="value" name="% of Revenue" radius={[4,4,0,0]} maxBarSize={26}
                label={{ position:"top", fontSize:9, formatter:(v:number)=>`${v>0?"+":""}${v}%` }}>
                {(costWaterfallData ?? COST_WATERFALL).map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Company Profile Radar" subtitle="BHP vs CBA — relative scoring across 6 dimensions">
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={RADAR_DATA} margin={{ top:4, right:16, bottom:4, left:16 }}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize:9, fill:SLATE }} />
              <PolarRadiusAxis angle={30} domain={[0,100]} tick={{ fontSize:8 }} />
              <Radar name="BHP" dataKey="BHP" stroke={NAV} fill={NAV} fillOpacity={0.18} strokeWidth={2} dot />
              <Radar name="CBA" dataKey="CBA" stroke={GOLD} fill={GOLD} fillOpacity={0.18} strokeWidth={2} dot />
              <Legend wrapperStyle={{ fontSize:9 }} />
              <Tooltip content={<TT />} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Section 6: Sector Aggregations table ────────────────────────── */}
      <div style={{ background:"#fff", borderRadius:12, border:"1px solid #e2e8f0", padding:"16px 20px", boxShadow:"0 1px 4px rgba(14,45,92,0.06)", marginBottom:16 }}>
        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:14 }}>
          <div style={{ width:3, height:20, background:RED, borderRadius:2 }} />
          <span style={{ fontSize:12, fontWeight:800, color:NAV, textTransform:"uppercase", letterSpacing:1 }}>§6 Sector Aggregations</span>
          <span style={{ fontSize:11, color:SLATE }}>— EP%, M:B, EEAI, TSR, Ke, EE Growth by Sector</span>
          <span style={{ marginLeft:"auto", fontSize:9, fontWeight:800, padding:"2px 8px", borderRadius:999, background:sectorAggRows?`${GREEN}18`:`${RED}18`, color:sectorAggRows?GREEN:RED, border:`1px solid ${sectorAggRows?GREEN:RED}33`, textTransform:"uppercase" }}>{sectorAggRows ? "● LIVE" : "illus."}</span>
        </div>
        <div style={{ overflowX:"auto" }}>
          <table style={{ borderCollapse:"collapse", width:"100%", fontSize:11 }}>
            <thead>
              <tr style={{ background:`${NAV}08` }}>
                {["Sector","EP% Deliv.","EP% Expct.","EEAI","M:B","TSR 1Y","Ke","EE Growth","EP Trend"].map(h => (
                  <th key={h} style={{ padding:"8px 12px", textAlign:"left", fontSize:10, color:SLATE, fontWeight:700, borderBottom:`2px solid ${NAV}22`, whiteSpace:"nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(sectorAggRows ?? EP_DEL_EXP.map(r => ({
                sector: r.sector,
                epDelivered: r.delivered, epExpected: r.expected, eeai: r.eeai,
                mb: null, tsr: null, ke: null, eeGrowth: null,
                epTrend: r.eeai >= 100 ? "positive" : "declining",
              } as SectorRow))).map((row, i) => (
                <tr key={row.sector}
                  onClick={() => drill.drillIntoSector(row.sector)}
                  style={{ background:i%2===0?"#fafbfe":"#fff", cursor:"pointer", transition:"background 0.1s" }}
                  onMouseEnter={e => (e.currentTarget.style.background=`${NAV}07`)}
                  onMouseLeave={e => (e.currentTarget.style.background=i%2===0?"#fafbfe":"#fff")}
                >
                  <td style={{ padding:"8px 12px", fontWeight:700, color:NAV }}>{row.sector}</td>
                  <td style={{ padding:"8px 12px", color:row.epDelivered !== null && row.epExpected !== null && row.epDelivered >= row.epExpected ? GREEN : RED, fontWeight:700 }}>{row.epDelivered !== null ? `${row.epDelivered}%` : "—"}</td>
                  <td style={{ padding:"8px 12px", color:SLATE }}>{row.epExpected !== null ? `${row.epExpected}%` : "—"}</td>
                  <td style={{ padding:"8px 12px" }}>
                    {row.eeai !== null ? (
                      <span style={{
                        padding:"2px 8px", borderRadius:999, fontSize:10, fontWeight:800,
                        background:row.eeai >= 100 ? `${GREEN}18` : `${RED}18`,
                        color:row.eeai >= 100 ? GREEN : RED,
                      }}>{row.eeai}</span>
                    ) : <span style={{ color:SLATE }}>—</span>}
                  </td>
                  <td style={{ padding:"8px 12px", color:NAV, fontWeight:600 }}>{row.mb !== null ? `${(row.mb as number).toFixed(2)}×` : "—"}</td>
                  <td style={{ padding:"8px 12px", color:row.tsr !== null && (row.tsr as number) > 0 ? GREEN : RED, fontWeight:600 }}>{row.tsr !== null ? `${row.tsr}%` : "—"}</td>
                  <td style={{ padding:"8px 12px", color:SLATE }}>{row.ke !== null ? `${row.ke}%` : "—"}</td>
                  <td style={{ padding:"8px 12px", color:row.eeGrowth !== null && (row.eeGrowth as number) > 0 ? GREEN : RED }}>{row.eeGrowth !== null ? `${row.eeGrowth}%` : "—"}</td>
                  <td style={{ padding:"8px 12px" }}>
                    <span style={{ fontSize:11, color:row.epTrend === "positive" ? GREEN : row.epTrend === "declining" ? RED : SLATE }}>
                      {row.epTrend === "positive" ? "▲ Positive" : row.epTrend === "declining" ? "▼ Declining" : "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ fontSize:10, color:SLATE, marginTop:8 }}>▶ Click a row to drill all charts to that sector</div>
      </div>

    </div>
  );
}
