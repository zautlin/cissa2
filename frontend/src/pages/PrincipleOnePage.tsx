import { useState } from "react";
import { Bar, Line, Scatter } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler, ScatterController,
  RadialLinearScale,
} from "chart.js";
import { Radar } from "react-chartjs-2";
import {
  roeKeByIndex, terKeByIndex, roeKeDistribution, terKeDistribution,
  epVsEpsCohorts, mbRatioByIndex,
  eeaiRequired, eeaiIndexCount,
  epDominantScatter,
  mbRatioSectorDist, mbRatioCompanyDist,
  terIntlUSA, terIntlUK, terIntlAUS,
  epPerShareGrowth, epPerShareBySector,
  epHeatmapData,
  tsrKeVsRoeKeScatter,
  cissaIndex2DScatter,
  esgMetricsData, esgKpis,
} from "../data/chartData";

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler, ScatterController,
  RadialLinearScale
);

const subSections = [
  { id: "1.1", label: "1.1  Cost of Equity (Ke)" },
  { id: "1.2", label: "1.2  Financial & Capital Bridge" },
  { id: "1.3", label: "1.3  Products & Services" },
  { id: "1.4", label: "1.4  Capital Market Predictor" },
  { id: "1.5", label: "1.5  Capital Market Assessment" },
];

const lineOpts = (yLabel = "%", minY?: number) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: "top" as const, labels: { boxWidth: 20, font: { size: 10 }, padding: 6 } },
    tooltip: { mode: "index" as const, intersect: false },
  },
  scales: {
    x: { ticks: { font: { size: 9 }, maxRotation: 45 }, grid: { color: "rgba(0,0,0,0.04)" } },
    y: {
      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}${yLabel}` },
      grid: { color: "rgba(0,0,0,0.04)" },
      ...(minY !== undefined ? { min: minY } : {}),
    },
  },
});

const barOpts = (yLabel = "") => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: "top" as const, labels: { boxWidth: 14, font: { size: 10 }, padding: 6 } },
    tooltip: { mode: "index" as const, intersect: false },
  },
  scales: {
    x: { ticks: { font: { size: 8 }, maxRotation: 0 }, grid: { display: false } },
    y: { ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}${yLabel}` }, grid: { color: "rgba(0,0,0,0.04)" } },
  },
});

const helpTexts: Record<string, string> = {
  "1.1": `The Cost of Equity Capital (Ke) serves as a datum or benchmark for the return achieved in the product and services market (ROE-Ke) and the return achieved in the capital market (TSR-Ke for an individual investor, and TER-Ke for a company as a whole). ROE-Ke — otherwise known as Economic Profitability — is the economic return on book value. Both TSR-Ke and TER-Ke tend towards zero as investors buy or sell shares at prices that ensure they at least earn Ke.`,
  "1.2": `Economic measures provide a more meaningful bridge than accounting metrics when seeking to link financial performance to capital market performance. For a zero-growth perpetuity, M:B Ratio = (ROE-Ke) / (Ke-g), where top-performing companies can expect M:B ratios between 2× and 4×.`,
  "1.3": `Economic measures are both more meaningful and more complete than accounting metrics when measuring a company's performance in the market for its products and services. EPS Growth and EP per Share Growth tend to move together irrespective of capital requirements — proving that economic measures are essential.`,
  "1.4": `Using economic metrics to measure product and service market performance provides a better predictor of likely capital market performance. EP Dominant companies — whose EP per Share Growth materially exceeds EPS Growth — deliver much higher TSR outcomes than EPS Dominant companies.`,
  "1.5": `Economic metrics like TSR-Ke and TSR Alpha are more meaningful than non-economic metrics like TSR and Relative TSR when assessing standalone capital market performance. TER Alpha strips out the risk-adjusted impact of underlying market movements, providing a more reliable measure of company-attributable wealth creation.`,
};

// ─── EP Heatmap component (CSS grid, no extra library) ─────────────────────
function EpHeatmapGrid() {
  const { sectors, years, values } = epHeatmapData;

  function heatColor(v: number): string {
    // v in [-3, +3] → red (negative) through white (zero) to green (positive)
    const norm = Math.max(-1, Math.min(1, v / 3));
    if (norm >= 0) {
      const g = Math.round(140 + 55 * norm);
      const r = Math.round(255 - 100 * norm);
      const b = Math.round(255 - 120 * norm);
      return `rgb(${r},${g},${b})`;
    } else {
      const r = Math.round(255);
      const g = Math.round(220 + 50 * norm);
      const b = Math.round(220 + 50 * norm);
      return `rgb(${r},${g},${b})`;
    }
  }

  function textColor(v: number): string {
    return Math.abs(v) > 1.5 ? "#fff" : "hsl(220 15% 20%)";
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.72rem", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ padding: "0.375rem 0.625rem", textAlign: "left", fontWeight: 700, color: "hsl(var(--foreground))", background: "hsl(var(--muted))", borderRadius: "4px 0 0 0" }}>
              Sector
            </th>
            {years.map(y => (
              <th key={y} style={{ padding: "0.375rem 0.5rem", textAlign: "center", fontWeight: 600, color: "hsl(var(--muted-foreground))", background: "hsl(var(--muted))", minWidth: "52px" }}>
                {y}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sectors.map((sector, si) => (
            <tr key={sector}>
              <td style={{ padding: "0.3rem 0.625rem", fontWeight: 600, color: "hsl(var(--foreground))", borderBottom: "1px solid hsl(var(--border))", whiteSpace: "nowrap" }}>
                {sector}
              </td>
              {values[si].map((val, yi) => (
                <td key={yi} style={{
                  padding: "0.3rem 0.25rem",
                  textAlign: "center",
                  background: heatColor(val),
                  color: textColor(val),
                  fontWeight: 600,
                  borderBottom: "1px solid rgba(255,255,255,0.3)",
                  borderRight: "1px solid rgba(255,255,255,0.3)",
                  transition: "opacity 150ms",
                }}>
                  {val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {/* Legend */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", fontWeight: 500 }}>EP Score:</span>
        {[
          { color: "rgb(255,120,120)", label: "−3 (Severe destruction)" },
          { color: "rgb(255,200,200)", label: "−1" },
          { color: "rgb(245,245,245)", label: "0 (Neutral)" },
          { color: "rgb(180,220,180)", label: "+1" },
          { color: "rgb(100,180,100)", label: "+3 (Strong creation)" },
        ].map(l => (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <div style={{ width: "16px", height: "12px", background: l.color, borderRadius: "2px", border: "1px solid rgba(0,0,0,0.1)" }} />
            <span style={{ fontSize: "0.625rem", color: "hsl(var(--muted-foreground))" }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PrincipleOnePage() {
  const [activeSection, setActiveSection] = useState("1.1");
  const [showHelp, setShowHelp] = useState(false);
  const [indexFilter, setIndexFilter] = useState("ASX 300");
  const [periodFilter, setPeriodFilter] = useState("2001–2024");

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* Breadcrumb section navigator */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginBottom: "0.5rem", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Principle 1 — A Recognition that Economic Measures are Better
        </div>
        <div className="breadcrumb-nav">
          {subSections.map(s => (
            <button
              key={s.id}
              className={`breadcrumb-step ${activeSection === s.id ? "active" : ""}`}
              onClick={() => setActiveSection(s.id)}
              data-testid={`tab-section-${s.id}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Controls row */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", fontWeight: 500 }}>Index:</span>
          {["ASX 300", "ASX 200", "S&P 500"].map(idx => (
            <button
              key={idx}
              className={`select-btn ${indexFilter === idx ? "active" : ""}`}
              style={{ background: indexFilter === idx ? "hsl(var(--primary))" : undefined, color: indexFilter === idx ? "#fff" : undefined }}
              onClick={() => setIndexFilter(idx)}
              data-testid={`filter-index-${idx.replace(/\s+/g, "-")}`}
            >
              {idx}
            </button>
          ))}
        </div>
        <div style={{ width: "1px", height: "20px", background: "hsl(var(--border))", margin: "0 0.25rem" }} />
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", fontWeight: 500 }}>Period:</span>
          {["2001–2024", "2010–2024", "2015–2024"].map(p => (
            <button
              key={p}
              className={`select-btn ${periodFilter === p ? "active" : ""}`}
              style={{ background: periodFilter === p ? "hsl(var(--primary))" : undefined, color: periodFilter === p ? "#fff" : undefined }}
              onClick={() => setPeriodFilter(p)}
              data-testid={`filter-period-${p}`}
            >
              {p}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: "auto" }}>
          <button
            className="select-btn"
            onClick={() => setShowHelp(v => !v)}
            style={{ background: showHelp ? "hsl(213 75% 22% / 0.1)" : undefined, borderColor: showHelp ? "hsl(var(--primary))" : undefined }}
            data-testid="button-toggle-help"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>
            </svg>
            {showHelp ? "Hide Guidance" : "Show Guidance"}
          </button>
        </div>
      </div>

      {/* Help panel */}
      {showHelp && (
        <div className="help-panel" style={{ marginBottom: "1.25rem" }}>
          <div style={{ fontWeight: 600, marginBottom: "0.375rem", color: "hsl(var(--primary))", fontSize: "0.8125rem" }}>
            Guidance — Section {activeSection}
          </div>
          <p>{helpTexts[activeSection]}</p>
        </div>
      )}

      {/* Section 1.1 — Cost of Equity */}
      {activeSection === "1.1" && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem", borderLeft: "3px solid hsl(var(--primary))" }}>
            <strong>ROE-Ke</strong> (Economic Profitability) is the economic return on book value.
            &nbsp;<span className="text-accent"><strong>TSR-Ke</strong></span> is the economic return on market value for an individual shareholder.
            &nbsp;<span style={{ color: "hsl(188 78% 35%)" }}><strong>TER-Ke</strong></span> is the wealth creation or economic return on market value on a whole-of-company basis.
            Each tends to converge towards zero over time — offset by management action.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Time Series of Historical ROE-Ke by Index</div>
              <div className="chart-card-subtitle">{indexFilter} · {periodFilter} · Economic Profitability (%)</div>
              <div style={{ height: "230px" }}>
                <Line data={roeKeByIndex} options={lineOpts("%")} />
              </div>
              <div style={{ marginTop: "0.75rem", overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      {["2001","2005","2010","2015","2019"].map(y => <th key={y}>{y}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["LT Avg", "10.6%","10.6%","10.6%","10.6%","10.6%"],
                      ["1 Year","6.7%","9.5%","10.9%","12.1%","14.8%"],
                      ["5 Years","—","9.7%","—","12.5%","13.9%"],
                      ["10 Years","—","—","9.2%","10.7%","12.9%"],
                    ].map(row => (
                      <tr key={row[0]}>
                        {row.map((cell, i) => (
                          <td key={i} style={{ fontWeight: i === 0 ? 600 : undefined }}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-title">Distribution of Historical ROE-Ke by Industry Sector</div>
              <div className="chart-card-subtitle">Number of sectors in {indexFilter} · {periodFilter}</div>
              <div style={{ height: "230px" }}>
                <Bar data={roeKeDistribution} options={{
                  ...barOpts("%"),
                  plugins: {
                    ...barOpts("%").plugins,
                    tooltip: {
                      callbacks: {
                        title: (items: any[]) => `ROE-Ke: ${items[0].label}%`,
                        label: (item: any) => `${item.raw} sectors`,
                      },
                    },
                  },
                }} />
              </div>
              <p style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.5rem", fontStyle: "italic" }}>
                Click on a bar to reveal names of sectors, then choose a sector for company-level view.
              </p>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Annualised TER-Ke (Wealth Creation) by Index</div>
              <div className="chart-card-subtitle">Annual, 3, 5 &amp; 10yr rolling — {indexFilter} · {periodFilter}</div>
              <div style={{ height: "200px" }}>
                <Line data={terKeByIndex} options={lineOpts("%", -45)} />
              </div>
              <div style={{ marginTop: "0.75rem", overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      {["2001","2005","2010","2015","2019"].map(y => <th key={y}>{y}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["1 Year","(26.9%)","(5.8%)","8.6%","3.2%","11.8%"],
                      ["3 Years","—","(1.0%)","4.3%","10.4%","10.8%"],
                      ["5 Years","—","(13.6%)","—","0.7%","6.8%"],
                      ["10 Years","—","—","—","—","6.8%"],
                    ].map(row => (
                      <tr key={row[0]}>
                        {row.map((cell, i) => (
                          <td key={i} style={{
                            fontWeight: i === 0 ? 600 : undefined,
                            color: i > 0 && cell.startsWith("(") ? "hsl(0 72% 51%)" : undefined,
                          }}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-title">Distribution of TER-Ke by Industry Sector</div>
              <div className="chart-card-subtitle">Number of sectors · Annualised Wealth Creation · {indexFilter}</div>
              <div style={{ height: "200px" }}>
                <Bar data={terKeDistribution} options={barOpts("%")} />
              </div>
              <div style={{ marginTop: "0.75rem" }}>
                <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>
                  <strong>Note.</strong> TER is a more robust measure of capital market return than TSR as traditionally defined.
                  TER-Ke is the annualised wealth creation outcome measured on a whole of company basis.
                  TSR-Ke measures wealth creation on an individual shareholder basis.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Section 1.2 — Financial & Capital Bridge */}
      {activeSection === "1.2" && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem", borderLeft: "3px solid hsl(38 60% 52%)" }}>
            <strong>M:B Ratio = (ROE − g) / (Ke − g)</strong> &nbsp; — or, equivalently, &nbsp;
            <strong>Intrinsic Market Value = Economic Profit / (Ke-g) + Book Value</strong>.
            Top-performing listed companies can expect an M:B ratio between <strong>2× and 4×</strong>.
            2× implies ROE-Ke of 5% with growth of 5%; 4× implies ROE-Ke of 15% with growth of 5%.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Time Series of Historical M:B Ratio by Index</div>
              <div className="chart-card-subtitle">{indexFilter} · {periodFilter}</div>
              <div style={{ height: "220px" }}>
                <Line data={mbRatioByIndex} options={lineOpts("×")} />
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-title">M:B Ratio Sensitivity Table</div>
              <div className="chart-card-subtitle">Market to Book = (ROE-Ke) / (Ke-g) · Ke = 10%</div>
              <div style={{ overflowX: "auto", marginTop: "0.25rem" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Sustainable ROE-Ke</th>
                      {["0%","1%","2%","3%","4%","5%","6%","7%","8%"].map(g => <th key={g}>g={g}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["9.0 (−1.0%)","0.90","0.89","0.88","0.86","0.83","0.80","0.75","0.67","0.50"],
                      ["10.0 (0.0%)","1.00","1.00","1.00","1.00","1.00","1.00","1.00","1.00","1.00"],
                      ["11.0 (1.0%)","1.10","1.11","1.13","1.14","1.17","1.20","1.25","1.33","1.50"],
                      ["12.0 (2.0%)","1.20","1.22","1.25","1.29","1.33","1.40","1.50","1.67","2.00"],
                      ["13.0 (3.0%)","1.30","1.33","1.38","1.43","1.50","1.60","1.75","2.00","2.50"],
                      ["15.0 (5.0%)","1.50","1.56","1.63","1.71","1.83","2.00","2.25","2.67","3.50"],
                    ].map((row, ri) => (
                      <tr key={ri}>
                        {row.map((cell, i) => (
                          <td key={i} style={{
                            fontWeight: i === 0 ? 600 : undefined,
                            background: parseFloat(cell) >= 2.0 ? "hsl(213 75% 22% / 0.1)" : undefined,
                            color: parseFloat(cell) >= 2.0 ? "hsl(213 75% 22%)" : undefined,
                          }}>
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ fontSize: "0.6875rem", marginTop: "0.5rem", color: "hsl(var(--muted-foreground))" }}>
                Highlighted cells (≥2.0×) represent the expected range for good-to-top performing companies.
              </p>
            </div>
          </div>

          {/* M:B Distribution Histograms */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">Distribution of M:B Ratio by Sector</div>
              <div className="chart-card-subtitle">{indexFilter} — number of sectors by M:B range</div>
              <div style={{ height: "210px" }}>
                <Bar data={mbRatioSectorDist} options={barOpts("×")} />
              </div>
            </div>
            <div className="chart-card">
              <div className="chart-card-title">Distribution of M:B Ratio by Company within Sector</div>
              <div className="chart-card-subtitle">{indexFilter} — Materials / Financials / Healthcare</div>
              <div style={{ height: "210px" }}>
                <Bar data={mbRatioCompanyDist} options={{
                  ...barOpts("×"),
                  plugins: {
                    ...barOpts("×").plugins,
                  },
                  scales: {
                    x: { ticks: { font: { size: 8 }, maxRotation: 0 }, grid: { display: false }, stacked: false },
                    y: { ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}×` }, grid: { color: "rgba(0,0,0,0.04)" } },
                  },
                }} />
              </div>
              <p style={{ fontSize: "0.6875rem", marginTop: "0.5rem", color: "hsl(var(--muted-foreground))" }}>
                Select a sector bar to drill down to company-level distribution.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Section 1.3 — Products & Services — FULLY IMPLEMENTED */}
      {activeSection === "1.3" && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem", borderLeft: "3px solid hsl(188 78% 35%)" }}>
            <strong style={{ color: "hsl(var(--primary))" }}>Section 1.3 — Products &amp; Services Market</strong>
            <p style={{ margin: "0.375rem 0 0" }}>{helpTexts["1.3"]}</p>
          </div>

          {/* Row 1: EP per Share Growth + Sector Time Series */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="chart-card" style={{ borderTop: "3px solid hsl(152 60% 40%)" }}>
              <div className="chart-card-title">EP per Share Growth — Cohort Comparison</div>
              <div className="chart-card-subtitle">{indexFilter} · {periodFilter} · EP Dominant vs EPS Dominant</div>
              <div style={{ height: "240px" }}>
                <Line data={epPerShareGrowth} options={{
                  ...lineOpts("%"),
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 20, font: { size: 9 }, padding: 6 } },
                    tooltip: { mode: "index" as const, intersect: false },
                  },
                }} />
              </div>
              <div style={{ marginTop: "0.625rem", padding: "0.625rem 0.875rem", background: "hsl(152 60% 96%)", borderRadius: "0.375rem", borderLeft: "3px solid hsl(152 60% 40%)" }}>
                <p style={{ margin: 0, fontSize: "0.6875rem", color: "hsl(152 60% 28%)", lineHeight: 1.5 }}>
                  <strong>Key insight:</strong> EP Dominant companies show EP/Share Growth of ~55% vs. EPS Growth of ~38% — demonstrating that economic measures reflect true value creation missed by EPS alone.
                </p>
              </div>
            </div>

            <div className="chart-card" style={{ borderTop: "3px solid hsl(213 75% 40%)" }}>
              <div className="chart-card-title">EP per Share by Sector — Time Series</div>
              <div className="chart-card-subtitle">{indexFilter} · Healthcare / Technology / Consumer Staples / Materials</div>
              <div style={{ height: "240px" }}>
                <Line data={epPerShareBySector} options={{
                  ...lineOpts("%"),
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 20, font: { size: 9 }, padding: 6 } },
                    tooltip: { mode: "index" as const, intersect: false },
                  },
                }} />
              </div>
              <div style={{ marginTop: "0.625rem", padding: "0.625rem 0.875rem", background: "hsl(213 75% 22% / 0.05)", borderRadius: "0.375rem", border: "1px solid hsl(213 75% 22% / 0.15)" }}>
                <p style={{ margin: 0, fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>
                  Technology sector EP/Share outpaces all others from 2013 onwards; Materials show persistent EP destruction consistent with commodity cycle headwinds.
                </p>
              </div>
            </div>
          </div>

          {/* Row 2: EP Heatmap */}
          <div className="chart-card" style={{ marginBottom: "1rem", borderTop: "3px solid hsl(213 75% 22%)" }}>
            <div className="chart-card-title" style={{ fontSize: "0.9375rem" }}>EP Score Heatmap — Sector × Year</div>
            <div className="chart-card-subtitle">Economic Profit score by sector · 2010–2019 · Normalised to [−3, +3] scale · {indexFilter}</div>
            <div style={{ marginTop: "0.75rem" }}>
              <EpHeatmapGrid />
            </div>
            <p style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.75rem", fontStyle: "italic" }}>
              EP Score = (ROE−Ke) × Book Equity normalised by sector peer median. Green = EP creation above Ke; Red = EP destruction below Ke.
            </p>
          </div>

          {/* Row 3: TSR-Ke vs ROE-Ke scatter + EPS/EP per Share scatter */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="chart-card" style={{ borderTop: "3px solid hsl(152 60% 40%)" }}>
              <div className="chart-card-title">TSR-Ke vs ROE-Ke — Capital Market Linkage</div>
              <div className="chart-card-subtitle">{indexFilter} · Annualised 10Y · Economic Profitability drives Wealth Creation</div>
              <div style={{ height: "280px" }}>
                <Scatter data={tsrKeVsRoeKeScatter} options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 14, font: { size: 9 }, padding: 6 } },
                    tooltip: {
                      callbacks: {
                        label: (ctx: any) => `${ctx.dataset.label}: ROE-Ke ${ctx.parsed.x > 0 ? "+" : ""}${ctx.parsed.x.toFixed(1)}% | TSR-Ke ${ctx.parsed.y > 0 ? "+" : ""}${ctx.parsed.y.toFixed(1)}%`,
                      },
                    },
                  },
                  scales: {
                    x: {
                      title: { display: true, text: "ROE-Ke % (Economic Profitability)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.05)" },
                    },
                    y: {
                      title: { display: true, text: "TSR-Ke % (Capital Market Wealth Creation)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.05)" },
                    },
                  },
                }} />
              </div>
            </div>

            <div className="chart-card" style={{ borderTop: "3px solid hsl(38 60% 52%)" }}>
              <div className="chart-card-title">CISSA Index — Alignment vs EP Growth</div>
              <div className="chart-card-subtitle">{indexFilter} companies · CISSA Principle Alignment (0–10) vs EP Growth (%)</div>
              <div style={{ height: "280px" }}>
                <Scatter data={cissaIndex2DScatter} options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 14, font: { size: 9 }, padding: 6 } },
                    tooltip: {
                      callbacks: {
                        label: (ctx: any) => {
                          const pt = ctx.raw as { x: number; y: number; label?: string };
                          return `${pt.label || ctx.dataset.label}: Alignment ${pt.x}/10 | EP Growth ${pt.y > 0 ? "+" : ""}${pt.y}%`;
                        },
                      },
                    },
                  },
                  scales: {
                    x: {
                      title: { display: true, text: "CISSA Principle Alignment Score (0–10)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 } },
                      grid: { color: "rgba(0,0,0,0.05)" },
                      min: 0, max: 11,
                    },
                    y: {
                      title: { display: true, text: "EP per Share Growth (%)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.05)" },
                    },
                  },
                }} />
              </div>
            </div>
          </div>

          {/* Row 4: ESG / Sustainability Panel */}
          <div className="chart-card" style={{ borderTop: "3px solid hsl(152 60% 40%)" }}>
            <div className="chart-card-title" style={{ fontSize: "0.9375rem" }}>ESG &amp; Sustainability Metrics by EP Cohort</div>
            <div className="chart-card-subtitle">6 ESG Dimensions · EP Dominant vs Middle vs EPS Dominant · {indexFilter}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem", marginTop: "0.75rem" }}>
              {/* Radar chart */}
              <div style={{ height: "280px" }}>
                <Radar data={esgMetricsData} options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 16, font: { size: 9 }, padding: 8 } },
                  },
                  scales: {
                    r: {
                      min: 0, max: 100,
                      ticks: { font: { size: 8 }, stepSize: 20 },
                      pointLabels: { font: { size: 9 } },
                      grid: { color: "rgba(0,0,0,0.06)" },
                    },
                  },
                }} />
              </div>
              {/* ESG KPI table */}
              <div style={{ overflowX: "auto" }}>
                <table className="data-table" style={{ fontSize: "0.7rem" }}>
                  <thead>
                    <tr>
                      <th>ESG Metric</th>
                      <th style={{ color: "hsl(152 60% 35%)" }}>EP Dominant</th>
                      <th style={{ color: "hsl(38 60% 45%)" }}>Middle</th>
                      <th style={{ color: "hsl(0 72% 40%)" }}>EPS Dominant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {esgKpis.map((row, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 500, color: "hsl(var(--foreground))", maxWidth: "160px" }}>{row.metric}</td>
                        <td style={{ fontWeight: 700, color: "hsl(152 60% 35%)", textAlign: "center" }}>{row.epDominant}</td>
                        <td style={{ color: "hsl(38 60% 45%)", textAlign: "center" }}>{row.middle}</td>
                        <td style={{ color: "hsl(0 72% 40%)", textAlign: "center" }}>{row.epsDominant}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p style={{ fontSize: "0.6125rem", color: "hsl(var(--muted-foreground))", marginTop: "0.5rem", fontStyle: "italic" }}>
                  Companies with strong EP alignment consistently outperform on ESG dimensions — confirming that economic and stakeholder value creation are complementary, not competing.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Section 1.4 — Capital Market Predictor */}
      {activeSection === "1.4" && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem", borderLeft: "3px solid hsl(152 60% 40%)" }}>
            <strong>EP Dominant companies</strong> (EP per Share Growth materially &gt; EPS Growth) delivered much higher TSR outcomes
            than <strong>EPS Dominant companies</strong> over the 10 years to 30 June 2018 on the ASX 500.
            This demonstrates that economic metrics are superior indicators of likely capital market performance.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">EP Dominant vs EPS Dominant — Capital Market Outcomes</div>
              <div className="chart-card-subtitle">ASX 500 · 10 Years to 30 June 2018</div>
              <div style={{ height: "260px" }}>
                <Bar data={epVsEpsCohorts} options={{
                  ...barOpts("%"),
                  scales: {
                    x: { ticks: { font: { size: 8 } }, grid: { display: false } },
                    y: {
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.04)" },
                    },
                  },
                }} />
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-card-title">Cohort Summary Table</div>
              <div className="chart-card-subtitle">ASX 500 · 10 Years to 30 June 2018</div>
              <div style={{ marginTop: "0.5rem" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Company Cohort</th>
                      <th>Companies</th>
                      <th>EPS Growth</th>
                      <th>EP/Share Growth</th>
                      <th>Ann. TSR</th>
                      <th>Ann. TSR-Ke</th>
                      <th>Ann. TSR Alpha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["EP Dominant", "39", "37.8%", "55.2%", "14.8%", "5.1%", "8.8%", true],
                      ["Middle Group", "89", "0.6%", "−1.2%", "7.4%", "−1.6%", "1.6%", false],
                      ["EPS Dominant", "152", "3.0%", "−34.0%", "5.7%", "−4.7%", "−0.9%", false],
                    ].map((row, ri) => (
                      <tr key={ri} style={{ fontWeight: row[7] ? 600 : undefined }}>
                        <td style={{ color: row[7] ? "hsl(var(--primary))" : undefined }}>{row[0]}</td>
                        <td>{row[1]}</td>
                        <td>{row[2]}</td>
                        <td style={{ color: String(row[3]).startsWith("−") ? "hsl(0 72% 51%)" : "hsl(152 60% 40%)" }}>{row[3]}</td>
                        <td>{row[4]}</td>
                        <td style={{ color: String(row[5]).startsWith("−") ? "hsl(0 72% 51%)" : undefined }}>{row[5]}</td>
                        <td style={{ color: String(row[6]).startsWith("−") ? "hsl(0 72% 51%)" : "hsl(152 60% 40%)" }}>{row[6]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: "0.875rem", display: "flex", flexDirection: "column", gap: "0.375rem" }}>
                {[
                  { label: "Cost of Equity (Ke)", value: "9.1%", color: "hsl(var(--primary))" },
                  { label: "Benchmark TSR", value: "9.8%", color: "hsl(38 60% 52%)" },
                  { label: "TSR Alpha Reference", value: "9.9%", color: "hsl(152 60% 40%)" },
                ].map(stat => (
                  <div key={stat.label} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "0.375rem 0.75rem",
                    background: "hsl(var(--muted))",
                    borderRadius: "0.375rem",
                    fontSize: "0.75rem",
                  }}>
                    <span style={{ color: "hsl(var(--muted-foreground))" }}>{stat.label}</span>
                    <span style={{ fontWeight: 700, color: stat.color }}>{stat.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* EPS Growth vs EP per Share Growth 4-Quadrant Scatter */}
          <div className="chart-card" style={{ marginBottom: "1rem", borderTop: "3px solid hsl(152 60% 40%)" }}>
            <div className="chart-card-title" style={{ fontSize: "0.9375rem" }}>EPS Growth vs EP per Share Growth — 4-Quadrant Analysis</div>
            <div className="chart-card-subtitle">ASX 200* · Companies categorised by growth cohort</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: "1rem", marginTop: "0.5rem" }}>
              <div style={{ height: "320px", position: "relative" }}>
                {/* Quadrant labels */}
                <div style={{ position: "absolute", top: "8px", right: "8px", fontSize: "0.6875rem", fontWeight: 700, color: "hsl(152 60% 35%)", background: "hsl(152 60% 95%)", padding: "0.2rem 0.5rem", borderRadius: "4px", zIndex: 1 }}>EP Dominant</div>
                <div style={{ position: "absolute", bottom: "8px", right: "8px", fontSize: "0.6875rem", fontWeight: 700, color: "hsl(0 72% 40%)", background: "hsl(0 72% 96%)", padding: "0.2rem 0.5rem", borderRadius: "4px", zIndex: 1 }}>EPS Dominant</div>
                <div style={{ position: "absolute", top: "8px", left: "8px", fontSize: "0.6875rem", fontWeight: 600, color: "hsl(var(--muted-foreground))", background: "hsl(var(--muted))", padding: "0.2rem 0.5rem", borderRadius: "4px", zIndex: 1 }}>Mixed</div>
                <div style={{ position: "absolute", bottom: "8px", left: "8px", fontSize: "0.6875rem", fontWeight: 600, color: "hsl(220 15% 45%)", background: "hsl(220 15% 92%)", padding: "0.2rem 0.5rem", borderRadius: "4px", zIndex: 1 }}>Poor Performers</div>
                <Scatter data={epDominantScatter} options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { position: "bottom" as const, labels: { boxWidth: 14, font: { size: 10 }, padding: 8 } },
                    tooltip: {
                      callbacks: {
                        label: (ctx: any) => `${ctx.dataset.label}: EPS ${ctx.parsed.x > 0 ? "+" : ""}${ctx.parsed.x}% / EP ${ctx.parsed.y > 0 ? "+" : ""}${ctx.parsed.y}%`,
                      },
                    },
                  },
                  scales: {
                    x: {
                      title: { display: true, text: "EPS Growth per Share (%)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.06)" },
                    },
                    y: {
                      title: { display: true, text: "EP per Share Growth (%)", font: { size: 10, weight: "bold" } },
                      ticks: { font: { size: 9 }, callback: (v: number | string) => `${v}%` },
                      grid: { color: "rgba(0,0,0,0.06)" },
                    },
                  },
                }} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                {[
                  { label: "EP Dominant", cos: 39, tsr: "14.8%", color: "hsl(152 60% 40%)", bg: "hsl(152 60% 95%)" },
                  { label: "Mixed / Middle", cos: 89, tsr: "7.4%", color: "hsl(38 60% 45%)", bg: "hsl(38 60% 96%)" },
                  { label: "EPS Dominant", cos: 152, tsr: "5.7%", color: "hsl(0 72% 45%)", bg: "hsl(0 72% 96%)" },
                  { label: "Poor Performers", cos: 27, tsr: "2.1%", color: "hsl(220 15% 45%)", bg: "hsl(220 15% 94%)" },
                ].map(c => (
                  <div key={c.label} style={{ padding: "0.625rem 0.875rem", background: c.bg, borderRadius: "0.5rem", borderLeft: `3px solid ${c.color}` }}>
                    <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: c.color, marginBottom: "0.125rem" }}>{c.label}</div>
                    <div style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))" }}>{c.cos} companies</div>
                    <div style={{ fontSize: "0.875rem", fontWeight: 700, color: c.color, marginTop: "0.125rem" }}>Ann. TSR {c.tsr}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* EEAI / EEA Index chart */}
          <div className="chart-card" style={{ borderTop: "3px solid hsl(213 75% 22%)" }}>
            <div className="chart-card-title" style={{ fontSize: "0.9375rem" }}>EEA Index — Economic Profitability Analysis</div>
            <div className="chart-card-subtitle">Screen 1.4.11 · Required to Justify Share Price vs Historical Average (Rolling 3Y) · {indexFilter}</div>
            <div style={{ height: "220px", marginTop: "0.5rem" }}>
              <Line data={eeaiRequired} options={{
                ...lineOpts("%"),
                plugins: {
                  ...lineOpts("%").plugins,
                  tooltip: { mode: "index" as const, intersect: false },
                },
              }} />
            </div>
            <div style={{ height: "80px", marginTop: "0.5rem" }}>
              <Bar data={eeaiIndexCount} options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: "top" as const, labels: { boxWidth: 14, font: { size: 9 }, padding: 4 } },
                  tooltip: { callbacks: { label: (ctx: any) => `${ctx.parsed.y} companies in EEA Index` } },
                },
                scales: {
                  x: { ticks: { font: { size: 8 }, maxRotation: 45 }, grid: { display: false } },
                  y: { ticks: { font: { size: 8 }, stepSize: 20 }, grid: { color: "rgba(0,0,0,0.04)" }, min: 0, max: 130 },
                },
              }} />
            </div>
            <p style={{ fontSize: "0.6875rem", color: "hsl(var(--muted-foreground))", marginTop: "0.375rem", fontStyle: "italic" }}>
              Companies in EEA Index counted annually — includes all ASX 300 companies with sufficient data to calculate EP scores.
            </p>
          </div>
        </div>
      )}

      {/* Section 1.5 — Capital Market Assessment (TER Alpha International) */}
      {activeSection === "1.5" && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem", borderLeft: "3px solid hsl(213 75% 22%)" }}>
            <p style={{ fontWeight: 600, marginBottom: "0.5rem", color: "hsl(var(--primary))" }}>Section 1.5 — Capital Market Assessment</p>
            <p>{helpTexts["1.5"]}</p>
          </div>

          {/* TER Alpha International Comparison — 3 panels */}
          <div style={{ marginBottom: "1rem" }}>
            <div style={{ fontSize: "0.8125rem", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "0.625rem" }}>
              TER-Ke &amp; TER Alpha — International Comparison · Annualised Wealth Creation by Market
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
              {[
                { label: "United States (S&P 500)", data: terIntlUSA, color: "hsl(213 75% 22%)" },
                { label: "United Kingdom (FTSE 100)", data: terIntlUK, color: "hsl(188 78% 35%)" },
                { label: "Australia (ASX 300)", data: terIntlAUS, color: "hsl(38 60% 52%)" },
              ].map(market => (
                <div key={market.label} className="chart-card" style={{ borderTop: `3px solid ${market.color}` }}>
                  <div className="chart-card-title" style={{ color: market.color }}>{market.label}</div>
                  <div className="chart-card-subtitle">TER-Ke (solid) vs TER Alpha (dashed) · 2005–2018</div>
                  <div style={{ height: "200px" }}>
                    <Line data={market.data} options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { position: "bottom" as const, labels: { boxWidth: 20, font: { size: 9 }, padding: 6 } },
                        tooltip: { mode: "index" as const, intersect: false },
                      },
                      scales: {
                        x: { ticks: { font: { size: 8 }, maxRotation: 45 }, grid: { color: "rgba(0,0,0,0.04)" } },
                        y: {
                          ticks: { font: { size: 8 }, callback: (v: number | string) => `${v}%` },
                          grid: { color: "rgba(0,0,0,0.04)" },
                        },
                      },
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary KPIs */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
            {[
              { market: "USA", terKe: "5.9%", terAlpha: "3.4%", period: "2005–2018" },
              { market: "UK", terKe: "3.2%", terAlpha: "1.2%", period: "2005–2018" },
              { market: "Australia", terKe: "6.0%", terAlpha: "3.8%", period: "2005–2018" },
            ].map(m => (
              <div key={m.market} className="kpi-card">
                <div style={{ fontWeight: 700, color: "hsl(var(--primary))", fontSize: "0.875rem", marginBottom: "0.5rem" }}>{m.market} · {m.period}</div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>Avg TER-Ke</span>
                  <span style={{ fontWeight: 700, color: "hsl(213 75% 35%)" }}>{m.terKe}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>Avg TER Alpha</span>
                  <span style={{ fontWeight: 700, color: "hsl(38 60% 45%)" }}>{m.terAlpha}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="help-panel">
            <strong>Note on TER Alpha:</strong> TER Alpha strips out the risk-adjusted impact of underlying market movements,
            isolating the company-attributable component of wealth creation. It provides a more reliable cross-market comparison
            than raw TER-Ke since it controls for differing market betas and macro conditions.
          </div>
        </div>
      )}

    </div>
  );
}
