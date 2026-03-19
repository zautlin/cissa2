import { useState } from "react";
import { Bar, Line } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend,
} from "chart.js";
import {
  roeKeByIndex, terKeByIndex, roeKeDistribution, terKeDistribution,
  epVsEpsCohorts, mbRatioByIndex,
} from "../data/chartData";

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend
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
              <div style={{ height: "240px" }}>
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

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="chart-card">
              <div className="chart-card-title">EP Dominant vs EPS Dominant — Capital Market Outcomes</div>
              <div className="chart-card-subtitle">ASX 500 · 10 Years to 30 June 2018</div>
              <div style={{ height: "280px" }}>
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
              <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.375rem" }}>
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
        </div>
      )}

      {/* Default for 1.3 and 1.5 */}
      {(activeSection === "1.3" || activeSection === "1.5") && (
        <div>
          <div className="help-panel" style={{ marginBottom: "1rem" }}>
            <p style={{ fontWeight: 600, marginBottom: "0.5rem", color: "hsl(var(--primary))" }}>
              Section {activeSection} — Analytical Screens
            </p>
            <p>{helpTexts[activeSection]}</p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
            {[
              `Distribution by Industry Sector (${indexFilter})`,
              `Distribution by Company within Sector`,
              `Time Series 1,3,5,10yr by Index`,
              `Time Series by Sector within Index`,
              `Time Series by Company within Sector`,
              `TER Alpha Analysis`,
            ].map((label, i) => (
              <div key={i} className="chart-card" style={{
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
                minHeight: "100px",
                justifyContent: "center",
                alignItems: "center",
                background: "hsl(var(--muted) / 0.4)",
                border: "1.5px dashed hsl(var(--border))",
                transition: "border-color 150ms, background 150ms",
              }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "hsl(var(--primary))"; (e.currentTarget as HTMLElement).style.background = "hsl(var(--primary) / 0.05)"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = ""; (e.currentTarget as HTMLElement).style.background = ""; }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <path d="M3 9h18M9 21V9"/>
                </svg>
                <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", textAlign: "center" }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
