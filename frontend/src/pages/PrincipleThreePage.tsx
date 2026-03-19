import { useState } from "react";
import { Line, Bar, Scatter, Bubble } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Title, Tooltip, Legend, Filler,
} from "chart.js";
import {
  terIntlUSA, terIntlUK, terIntlAUS, terAlphaTimeSeries,
  wealthCreationAbsolute, tsrTerEpBubble, ecfDividendSplit,
  terKeByIndex, terKeDistribution, epVsEpsFocusOutcome,
} from "../data/chartData";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend, Filler);

const subSections = [
  { id: "3.1", label: "TER & TSR Overview" },
  { id: "3.2", label: "TER Alpha" },
  { id: "3.3", label: "ECF Decomposition" },
  { id: "3.4", label: "International TER" },
  { id: "3.5", label: "Wealth Creation" },
];

const helpTexts: Record<string, string> = {
  "3.1": "TER (Total Equity Return) measures the return delivered to shareholders. TER-Ke strips out the required return, isolating true wealth creation. Annualised TER-Ke is more meaningful than raw TSR because it accounts for the cost of equity across 1Y, 3Y, 5Y, and 10Y intervals.",
  "3.2": "TER Alpha goes further than TER-Ke by removing the risk-adjusted market movement (RA_MM). This isolates company-attributable wealth creation from macro effects. RA_MM = (Rm − Ke) × Beta-contribution, stripping passive market tailwinds.",
  "3.3": "Economic Cash Flow (ECF = Dividends + Capital Gains) is the total cash delivered per share. Non-Div ECF isolates the capital appreciation component. This decomposition shows whether wealth is being distributed (dividends) or reinvested (capital growth).",
  "3.4": "TER-Ke comparisons across Australia, USA, and UK reveal cross-market wealth creation dynamics. Markets where TER-Ke is persistently positive have companies delivering genuine EP above their cost of equity.",
  "3.5": "Absolute wealth creation (WC) in $billions shows the aggregate investor wealth added or destroyed each year. WC_TERA is risk-adjusted — it strips the passive market tailwind to show only company-driven wealth creation.",
};

const lineOpts = (title: string, yLabel = "%") => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } }, title: { display: false }, tooltip: { mode: "index" as const } },
  scales: {
    x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}${yLabel}` }, title: { display: true, text: yLabel === "%" ? "% p.a." : yLabel, font: { size: 10 } } },
  }
});

const barOpts = (title: string) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } }, title: { display: false } },
  scales: {
    x: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `$${v}B` } },
  }
});

export default function PrincipleThreePage() {
  const [activeSection, setActiveSection] = useState("3.1");
  const [indexFilter, setIndexFilter] = useState("ASX 200");
  const [periodFilter, setPeriodFilter] = useState("1Y Annualised");

  return (
    <div className="principle-page">
      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <label className="filter-label">Index</label>
          <select className="filter-select" value={indexFilter} onChange={e => setIndexFilter(e.target.value)}>
            <option>ASX 200</option><option>ASX 300</option><option>ASX 100</option>
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label">Period</label>
          <select className="filter-select" value={periodFilter} onChange={e => setPeriodFilter(e.target.value)}>
            <option>1Y Annualised</option><option>3Y Annualised</option><option>5Y Annualised</option><option>10Y Annualised</option>
          </select>
        </div>
      </div>

      {/* Breadcrumbs */}
      <div className="breadcrumb-nav">
        {subSections.map(s => (
          <button
            key={s.id}
            className={`breadcrumb-step ${activeSection === s.id ? "active" : ""}`}
            onClick={() => setActiveSection(s.id)}
            data-testid={`tab-section-${s.id}`}
          >
            <span className="breadcrumb-id">{s.id}</span>
            <span className="breadcrumb-label">{s.label}</span>
          </button>
        ))}
      </div>

      {/* Help text */}
      <div className="section-panel" style={{ marginBottom: "1rem" }}>
        <div className="section-panel-header">
          <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "hsl(var(--primary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Principle 3 — Capital Market Returns
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.83rem", color: "hsl(215 25% 45%)", lineHeight: 1.6 }}>{helpTexts[activeSection]}</p>
      </div>

      {/* ── Section 3.1 — TER & TSR Overview ── */}
      {activeSection === "3.1" && (
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-card-title">Annualised TER-Ke (Wealth Creation) by Index</div>
            <div className="chart-card-subtitle">{indexFilter} · Annual, 3, 5 &amp; 10yr rolling · {periodFilter}</div>
            <div style={{ height: 260 }}>
              <Line data={terKeByIndex} options={lineOpts("TER-Ke by Index")} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">Distribution of TER-Ke by Industry Sector</div>
            <div className="chart-card-subtitle">Number of sectors · Annualised Wealth Creation · {indexFilter}</div>
            <div style={{ height: 260 }}>
              <Bar data={terKeDistribution} options={{ ...barOpts("TER-Ke Distribution"), scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">EP Focus vs EPS Focus — Long-Term Outcome Comparison</div>
            <div className="chart-card-subtitle">EP-focused vs EPS-focused companies: EP/Share Growth and TSR over 1–10 year horizons</div>
            <div style={{ height: 280 }}>
              <Bar data={epVsEpsFocusOutcome} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}%` } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── Section 3.2 — TER Alpha ── */}
      {activeSection === "3.2" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">TER Alpha — Company-Attributable Wealth Creation</div>
            <div className="chart-card-subtitle">TER-Ke minus RA_MM (market risk adjustment) · {indexFilter} · 2005–2018</div>
            <div style={{ height: 320 }}>
              <Line data={terAlphaTimeSeries} options={lineOpts("TER Alpha")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">TER Alpha Components — Formula Reference</div>
            <div className="chart-card-subtitle">RA_MM = (Rm − Ke) × (Ke − Rf) / MRP · strips passive market tailwind</div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th><th>Formula</th><th>Interpretation</th><th>ASX 200 Avg (2015–2018)</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["TER", "Geometric mean of ECF / Open MC", "Raw total equity return", "10.4%"],
                    ["Ke", "Rf + Beta × MRP", "Required cost of equity", "8.1%"],
                    ["TER-Ke", "TER − Ke", "Excess return (wealth creation)", "+2.3%"],
                    ["Rm", "Geometric mean of market index return", "Market return", "9.8%"],
                    ["RA_MM", "(Rm − Ke) × (Ke − Rf) / MRP", "Risk-adjusted market adjustment", "+0.9%"],
                    ["TER Alpha", "TER-Ke − RA_MM", "Company-driven wealth creation", "+1.4%"],
                  ].map(([m, f, i, v]) => (
                    <tr key={m as string}>
                      <td style={{ fontWeight: 600, color: "hsl(var(--primary))" }}>{m}</td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.78rem" }}>{f}</td>
                      <td>{i}</td>
                      <td style={{ fontWeight: 600, color: parseFloat(v as string) >= 0 ? "hsl(152 60% 35%)" : "hsl(0 70% 45%)" }}>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Section 3.3 — ECF Decomposition ── */}
      {activeSection === "3.3" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">ECF: Dividends vs Capital Gains — ASX 200 ($B)</div>
            <div className="chart-card-subtitle">Economic Cash Flow decomposition · 2008–2018 · Positive = wealth delivered · Negative = capital destruction</div>
            <div style={{ height: 300 }}>
              <Bar data={ecfDividendSplit} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `$${v}B` } } } }} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">ECF Formula Breakdown</div>
            <div className="chart-card-subtitle">Economic Cash Flow (ECF) = Non-Div ECF + Dividends</div>
            <table className="data-table">
              <thead><tr><th>Component</th><th>Formula</th><th>2018 ($B)</th></tr></thead>
              <tbody>
                {[
                  ["ECF (Total)", "LAG_MC × (1 + FY_TSR) − MC", "86.4"],
                  ["Dividends", "Cash dividends paid", "38.2"],
                  ["Non-Div ECF", "ECF − Dividends", "48.2"],
                  ["Franking Credit", "Div/(1−t) × t × fc%", "+3.8"],
                ].map(([c,f,v]) => (
                  <tr key={c as string}><td style={{ fontWeight: 600 }}>{c}</td><td style={{ fontFamily: "monospace", fontSize: "0.78rem" }}>{f}</td><td style={{ fontWeight: 600, color: "hsl(152 60% 35%)" }}>${v}B</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">ECF Yield Trend — {indexFilter}</div>
            <div className="chart-card-subtitle">Dividend yield vs total ECF yield over time</div>
            <div style={{ height: 220 }}>
              <Line data={{ labels: ["2008","2010","2012","2014","2016","2018"], datasets: [
                { label: "Total ECF Yield", data: [8.2, 9.8, 7.4, 10.2, 9.8, 10.8], borderColor: "hsl(213 75% 40%)", backgroundColor: "transparent", tension: 0.3 },
                { label: "Dividend Yield", data: [4.8, 4.2, 4.8, 5.1, 5.4, 5.2], borderColor: "hsl(152 60% 40%)", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
              ]}} options={lineOpts("ECF Yield")} />
            </div>
          </div>
        </div>
      )}

      {/* ── Section 3.4 — International TER ── */}
      {activeSection === "3.4" && (
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-card-title">TER-Ke — Australia (ASX 200)</div>
            <div className="chart-card-subtitle">Annual, 3Y, 5Y, 10Y · 2005–2018</div>
            <div style={{ height: 240 }}>
              <Line data={terIntlAUS} options={lineOpts("TER-Ke AUS")} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">TER-Ke — United States (S&amp;P 500)</div>
            <div className="chart-card-subtitle">Annual, 3Y, 5Y, 10Y · 2005–2018</div>
            <div style={{ height: 240 }}>
              <Line data={terIntlUSA} options={lineOpts("TER-Ke USA")} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">TER-Ke — United Kingdom (FTSE 100)</div>
            <div className="chart-card-subtitle">Annual, 3Y, 5Y, 10Y · 2005–2018</div>
            <div style={{ height: 240 }}>
              <Line data={terIntlUK} options={lineOpts("TER-Ke UK")} />
            </div>
          </div>
          <div className="chart-card">
            <div className="chart-card-title">International TER-Ke Comparison — 10Y Annualised</div>
            <div className="chart-card-subtitle">Australia vs USA vs UK · Long-run wealth creation above cost of equity</div>
            <div style={{ height: 240 }}>
              <Bar data={{ labels: ["2005","2007","2009","2011","2013","2015","2017"], datasets: [
                { label: "Australia", data: [1.8,2.4,0.8,1.4,2.1,1.5,2.2], backgroundColor: "hsl(213 75% 40% / 0.8)" },
                { label: "USA", data: [2.4,3.1,1.2,2.8,3.4,2.8,3.8], backgroundColor: "hsl(38 60% 52% / 0.8)" },
                { label: "UK", data: [1.2,1.8,0.4,1.0,1.4,0.8,1.4], backgroundColor: "hsl(152 60% 40% / 0.8)" },
              ]}} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { callback: (v: any) => `${v}%` } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── Section 3.5 — Wealth Creation ── */}
      {activeSection === "3.5" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Absolute Wealth Created — ASX 200 ($B)</div>
            <div className="chart-card-subtitle">WC (bars) = Open MC × (1+TER)ⁿ − Open MC × (1+Ke)ⁿ · WC_TERA (line) = risk-adjusted version · 2005–2018</div>
            <div style={{ height: 300 }}>
              <Bar data={wealthCreationAbsolute} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { callback: (v: any) => `$${v}B` } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">TSR-Ke vs TER-Ke vs EP% — Company Bubble Chart</div>
            <div className="chart-card-subtitle">Bubble size = market cap · X = EP% (Economic Profitability) · Y = TER (Equity Return) · Colour = cohort</div>
            <div style={{ height: 320 }}>
              <Bubble data={tsrTerEpBubble} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "EP% (Economic Profitability)", font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "TER % p.a.", font: { size: 10 } } } } }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
