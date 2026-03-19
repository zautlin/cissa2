import { Link } from "wouter";
import { Bar, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { roeKeByIndex, terKeByIndex, mbRatioByIndex } from "../data/chartData";

// ─── Inline mini bow wave for hero section ─────────────────────────────────
function bellCurve(years: number[], peakYear: number, peakValue: number, sigma: number): number[] {
  return years.map(y => {
    const d = y - peakYear;
    return +(peakValue * Math.exp(-(d * d) / (2 * sigma * sigma))).toFixed(2);
  });
}
const yearOffsets = Array.from({ length: 26 }, (_, i) => i - 10);
const yearLabels = yearOffsets.map(o => (2014 + o).toString());
const baselineData = bellCurve(yearOffsets, 3, 350, 6);
const newData = yearOffsets.map((o, i) => o >= 0 ? bellCurve(yearOffsets, 5, 720, 8)[i] : null);
const heroBowWaveData = {
  labels: yearLabels,
  datasets: [
    {
      label: "Baseline EP Expectations",
      data: baselineData,
      borderColor: "hsl(38 70% 48%)",
      backgroundColor: "hsl(38 70% 48% / 0.15)",
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.5,
    },
    {
      label: "New EP Expectations",
      data: newData as (number | null)[],
      borderColor: "hsl(213 75% 40%)",
      backgroundColor: "hsl(213 75% 40% / 0.12)",
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.5,
    },
  ],
};
const heroBowWaveOptions: any = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: "top" as const,
      labels: { boxWidth: 20, font: { size: 10 }, padding: 8, usePointStyle: true, pointStyle: "line" },
    },
    tooltip: { mode: "index" as const, intersect: false },
  },
  scales: {
    x: {
      ticks: { font: { size: 8 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
      grid: { color: "rgba(0,0,0,0.04)" },
    },
    y: {
      title: { display: true, text: "Economic Profit ($m)", font: { size: 9 }, color: "hsl(220 15% 50%)" },
      ticks: { font: { size: 8 } },
      grid: { color: "rgba(0,0,0,0.04)" },
      min: 0,
    },
  },
};

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler
);

const kpis = [
  { label: "Avg ROE-Ke (ASX 300)", value: "10.6%", delta: "+0.4%", direction: "positive", note: "LT Avg Economic Profitability" },
  { label: "Avg TER-Ke (10yr Ann.)", value: "6.8%", delta: "+1.2%", direction: "positive", note: "Annualised Wealth Creation" },
  { label: "Avg M:B Ratio", value: "3.7×", delta: "-0.2×", direction: "neutral", note: "Market to Book" },
  { label: "EP Dominant TSR", value: "14.8%", delta: "vs 5.7% EPS Dom.", direction: "positive", note: "10yr Annualised TSR" },
  { label: "Cost of Equity (Ke)", value: "10.0%", delta: "Benchmark rate", direction: "neutral", note: "ASX 300 Long-run estimate" },
];

const principles = [
  { number: 1, label: "Economic Measures are Better", completion: 85, color: "hsl(213 75% 22%)", path: "/principles/1" },
  { number: 2, label: "Primary Focus on the Longer Term", completion: 40, color: "hsl(213 65% 35%)", path: "/principles/2" },
  { number: 3, label: "Central Role of Creativity & Innovation", completion: 30, color: "hsl(213 55% 45%)", path: "/principles/1" },
  { number: 4, label: "Focus on All Stakeholders", completion: 20, color: "hsl(213 45% 55%)", path: "/principles/1" },
  { number: 5, label: "Clear Purpose by Noble Intent", completion: 15, color: "hsl(213 35% 62%)", path: "/principles/1" },
  { number: 6, label: "Appreciation that More is Not Always Better", completion: 10, color: "hsl(213 25% 70%)", path: "/principles/1" },
];

const commonLineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: "top" as const,
      labels: {
        boxWidth: 24,
        font: { size: 10 },
        padding: 8,
      },
    },
    tooltip: { mode: "index" as const, intersect: false },
  },
  scales: {
    x: {
      ticks: { font: { size: 9 }, maxRotation: 45 },
      grid: { color: "rgba(0,0,0,0.04)" },
    },
    y: {
      ticks: {
        font: { size: 9 },
        callback: (v: number | string) => `${v}%`,
      },
      grid: { color: "rgba(0,0,0,0.04)" },
    },
  },
};

const mbOptions = {
  ...commonLineOptions,
  scales: {
    ...commonLineOptions.scales,
    y: {
      ...commonLineOptions.scales.y,
      ticks: {
        font: { size: 9 },
        callback: (v: number | string) => `${v}×`,
      },
    },
  },
};

export default function DashboardHome() {
  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* ── EP Bow Wave Hero Banner ── */}
      <div className="chart-card" style={{
        marginBottom: "1.5rem",
        borderTop: "3px solid hsl(213 75% 22%)",
        background: "linear-gradient(135deg, hsl(213 75% 22% / 0.03) 0%, hsl(38 60% 52% / 0.04) 100%)",
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 420px", gap: "1.5rem", alignItems: "center" }}>
          {/* Left: explanation */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.5rem" }}>
              <div style={{
                background: "hsl(38 60% 52%)", color: "#fff",
                fontSize: "0.625rem", fontWeight: 700,
                padding: "0.1875rem 0.625rem", borderRadius: "999px",
                textTransform: "uppercase", letterSpacing: "0.05em",
              }}>Signature Concept</div>
              <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>Principle 2</span>
            </div>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "hsl(var(--primary))", margin: "0 0 0.375rem 0", lineHeight: 1.25 }}>
              The EP Bow Wave
            </h2>
            <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.65, margin: "0 0 0.875rem 0" }}>
              A company's market capitalisation equals its book equity plus the present value of its entire expected Economic Profit stream — the EP Bow Wave. The pair of waves reveals wealth created or destroyed during any measurement period.
            </p>
            <div style={{ display: "flex", gap: "0.625rem", flexWrap: "wrap" }}>
              <Link href="/principles/2" data-testid="link-bow-wave"
                style={{
                  display: "inline-flex", alignItems: "center", gap: "0.375rem",
                  padding: "0.5rem 1rem",
                  background: "hsl(213 75% 22%)", color: "white",
                  borderRadius: "0.375rem", fontSize: "0.75rem", fontWeight: 700,
                  textDecoration: "none", whiteSpace: "nowrap",
                }}>
                Explore the Bow Wave
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="m9 18 6-6-6-6"/>
                </svg>
              </Link>
              <Link href="/principles/1" data-testid="link-start-principles"
                style={{
                  display: "inline-flex", alignItems: "center", gap: "0.375rem",
                  padding: "0.5rem 1rem",
                  background: "transparent",
                  border: "1px solid hsl(var(--border))",
                  color: "hsl(var(--foreground))",
                  borderRadius: "0.375rem", fontSize: "0.75rem", fontWeight: 600,
                  textDecoration: "none", whiteSpace: "nowrap",
                }}>
                Start with Principle 1
              </Link>
            </div>
          </div>
          {/* Right: mini bow wave chart */}
          <div>
            <div style={{ height: "200px" }}>
              <Line data={heroBowWaveData} options={heroBowWaveOptions} />
            </div>
            <div style={{ display: "flex", justifyContent: "center", gap: "1.5rem", marginTop: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
                <div style={{ width: "20px", height: "2.5px", background: "hsl(38 70% 48%)", borderRadius: "2px" }} />
                Baseline expectations (T₀)
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
                <div style={{ width: "20px", height: "2.5px", background: "hsl(213 75% 40%)", borderRadius: "2px" }} />
                New expectations (End)
              </div>
            </div>
            <div style={{ textAlign: "center", marginTop: "0.375rem" }}>
              <span style={{
                fontSize: "0.6875rem", fontWeight: 700,
                color: "hsl(152 60% 35%)",
                background: "hsl(152 60% 95%)",
                padding: "0.1875rem 0.625rem", borderRadius: "999px",
                border: "1px solid hsl(152 60% 75%)",
              }}>
                ▲ $3.1b enhancement · Cochlear (COH)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        {kpis.map(k => (
          <div key={k.label} className="kpi-card" data-testid={`kpi-${k.label.replace(/\s+/g, "-").toLowerCase()}`}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value animate-count">{k.value}</div>
            <div className={`kpi-delta ${k.direction}`}>
              {k.direction === "positive" && (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="m18 15-6-6-6 6"/>
                </svg>
              )}
              {k.direction === "negative" && (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="m6 9 6 6 6-6"/>
                </svg>
              )}
              {k.delta}
            </div>
            <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.25rem" }}>
              {k.note}
            </div>
          </div>
        ))}
      </div>

      {/* Two-column: charts + principles */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "1rem", marginBottom: "1rem" }}>

        {/* ROE-Ke time series */}
        <div className="chart-card">
          <div className="chart-card-title">Economic Profitability (ROE-Ke) by Index</div>
          <div className="chart-card-subtitle">Time series of historical annualised ROE-Ke — ASX 300</div>
          <div style={{ height: "220px" }}>
            <Line data={roeKeByIndex} options={commonLineOptions} />
          </div>
        </div>

        {/* Principles progress */}
        <div className="chart-card">
          <div className="chart-card-title">Six CISSA Principles</div>
          <div className="chart-card-subtitle">Navigate the Principles Menu</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.25rem" }}>
            {principles.map(p => (
              <Link href={p.path} key={p.number}
                style={{ textDecoration: "none", display: "block", cursor: "pointer" }}
                data-testid={`link-principle-${p.number}`}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.2rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <div style={{
                      width: "20px", height: "20px", borderRadius: "50%",
                      background: p.color, color: "#fff",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: "0.625rem", fontWeight: 700, flexShrink: 0,
                    }}>
                      {p.number}
                    </div>
                    <span style={{ fontSize: "0.6875rem", color: "hsl(var(--foreground))", fontWeight: 500, lineHeight: 1.3 }}>
                      {p.label}
                    </span>
                  </div>
                  <span style={{ fontSize: "0.625rem", color: "hsl(var(--muted-foreground))", flexShrink: 0, marginLeft: "0.5rem" }}>
                    {p.completion}%
                  </span>
                </div>
                <div className="principle-bar">
                  <div className="principle-bar-fill" style={{ width: `${p.completion}%`, background: p.color }} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* TER-Ke + M:B row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <div className="chart-card">
          <div className="chart-card-title">Annualised Wealth Creation (TER-Ke) by Index</div>
          <div className="chart-card-subtitle">Annual, 3, 5 &amp; 10yr rolling — ASX 300 · 2001–2019</div>
          <div style={{ height: "200px" }}>
            <Line data={terKeByIndex} options={{
              ...commonLineOptions,
              scales: {
                ...commonLineOptions.scales,
                y: {
                  ...commonLineOptions.scales.y,
                  ticks: {
                    font: { size: 9 },
                    callback: (v: number | string) => `${v}%`,
                  },
                  min: -45,
                },
              },
            }} />
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-card-title">Market to Book Ratio (M:B) by Index</div>
          <div className="chart-card-subtitle">Historical M:B ratio — ASX 300 · 2001–2019</div>
          <div style={{ height: "200px" }}>
            <Line data={mbRatioByIndex} options={mbOptions} />
          </div>
        </div>
      </div>

      {/* Menu quick-access */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
        {[
          {
            title: "Principles Menu",
            desc: "Six CISSA Principles with education, research outcomes, and analytical tools. Left-click for guidance, right-click for data.",
            path: "/principles/1",
            icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
            color: "hsl(213 75% 22%)",
          },
          {
            title: "Outputs Menu",
            desc: "How wealth is created in the product and capital markets — TSR-Ke short-term focus and long-term sustainable wealth creation.",
            path: "/outputs",
            icon: "M3 3h18v18H3zM3 9h18M9 21V9",
            color: "hsl(38 60% 52%)",
          },
          {
            title: "Underlying Data",
            desc: "Access the underlying data organised by the components of performance achieved in the product & service market and capital market.",
            path: "/underlying-data",
            icon: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z",
            color: "hsl(188 78% 35%)",
          },
          {
            title: "Reports",
            desc: "Research papers, company EP bow wave analyses, methodology documentation, and index-level annual wealth creation reports.",
            path: "/reports",
            icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8",
            color: "hsl(213 55% 45%)",
          },
        ].map(m => (
          <Link href={m.path} key={m.title}
            style={{ textDecoration: "none" }}
            data-testid={`link-menu-${m.title.replace(/\s+/g, "-").toLowerCase()}`}>
            <div className="chart-card" style={{
              cursor: "pointer",
              transition: "box-shadow 150ms ease, transform 150ms ease",
              borderLeft: `4px solid ${m.color}`,
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.1)";
                (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = "";
                (e.currentTarget as HTMLElement).style.transform = "";
              }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.5rem" }}>
                <div style={{
                  width: "32px", height: "32px", borderRadius: "0.5rem",
                  background: `${m.color}22`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={m.color} strokeWidth="2">
                    <path d={m.icon}/>
                  </svg>
                </div>
                <span style={{ fontWeight: 600, fontSize: "0.875rem", color: "hsl(var(--foreground))" }}>
                  {m.title}
                </span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth="2"
                  style={{ marginLeft: "auto" }}>
                  <path d="m9 18 6-6-6-6"/>
                </svg>
              </div>
              <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>
                {m.desc}
              </p>
            </div>
          </Link>
        ))}
      </div>

    </div>
  );
}
