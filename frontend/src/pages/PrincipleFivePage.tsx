import { useState } from "react";
import { Line, Bar, Radar, Scatter } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, RadialLinearScale, Title, Tooltip, Legend, Filler,
} from "chart.js";
import {
  costStructureBySector, revenueGrowthByInterval, eeGrowthBySector,
  roaBySector, profitMarginBySector, mbRatioIntervals, assetIntensityBySector,
  econEquityMultiplier, effectiveTaxRateTimeSeries, revVsEeGrowthScatter,
  esgMetricsData, esgKpis, keRoeTriangle,
} from "../data/chartData";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, RadialLinearScale, Title, Tooltip, Legend, Filler);

const subSections = [
  { id: "5.1", label: "Cost Structure" },
  { id: "5.2", label: "Revenue & EE Growth" },
  { id: "5.3", label: "ROA & Profit Margin" },
  { id: "5.4", label: "Asset Intensity" },
  { id: "5.5", label: "ESG & Sustainability" },
];

const helpTexts: Record<string, string> = {
  "5.1": "Cost structure analysis breaks total revenue into Operating Cost, Non-Operating Cost, Tax Cost, Extraordinary Cost, and Net Profit Margin. Sector differences reveal structural profitability drivers. Op Cost Margin = Op Cost / Revenue. All four cost intervals (1Y, 3Y, 5Y, 10Y) are available.",
  "5.2": "Revenue growth and Economic Equity (EE) growth are key drivers of long-run EP. Revenue delta and EE delta are calculated at 1Y, 3Y, 5Y, and 10Y annualised intervals. EE growth = (EEₙ − EEₙ₋₁) / |EEₙ₋₁|. Persistent EE growth above cost of equity indicates compounding value creation.",
  "5.3": "Return on Assets (ROA = PAT / Calc Assets) and Profit Margin (PAT / Revenue) at multiple intervals reveal operational efficiency trends. Annualised ROA smooths volatility and highlights structural performance differences across sectors.",
  "5.4": "Asset intensity ratios — FA Intensity (Fixed Assets / Revenue), GW Intensity (Goodwill / Revenue), OA Intensity (Operating Assets / Revenue) — reveal capital structure differences. High FA intensity sectors (Utilities, Energy) require more physical capital per dollar of revenue. Economic Equity Multiplier = Calc Assets / |EE_open|.",
  "5.5": "ESG and Sustainability metrics are evaluated across six dimensions. Companies in the EP Dominant cohort tend to show better long-term ESG alignment, consistent with the CISSA principle that genuine Economic Profit creates sustainable value for all stakeholders.",
};

const barOpts = (yLabel = "%") => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } } },
  scales: {
    x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}${yLabel}` } },
  }
});

const lineOpts = (yLabel = "%") => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: "bottom" as const, labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { mode: "index" as const } },
  scales: {
    x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } },
    y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}${yLabel}` } },
  }
});

export default function PrincipleFivePage() {
  const [activeSection, setActiveSection] = useState("5.1");
  const [indexFilter, setIndexFilter] = useState("ASX 200");
  const [intervalFilter, setIntervalFilter] = useState("3Y Annualised");

  return (
    <div className="principle-page">
      <div className="filter-bar">
        <div className="filter-group">
          <label className="filter-label">Index</label>
          <select className="filter-select" value={indexFilter} onChange={e => setIndexFilter(e.target.value)}>
            <option>ASX 200</option><option>ASX 300</option><option>ASX 100</option>
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label">Interval</label>
          <select className="filter-select" value={intervalFilter} onChange={e => setIntervalFilter(e.target.value)}>
            <option>1Y</option><option>3Y Annualised</option><option>5Y Annualised</option><option>10Y Annualised</option>
          </select>
        </div>
      </div>

      <div className="breadcrumb-nav">
        {subSections.map(s => (
          <button key={s.id} className={`breadcrumb-step ${activeSection === s.id ? "active" : ""}`}
            onClick={() => setActiveSection(s.id)} data-testid={`tab-section-${s.id}`}>
            <span className="breadcrumb-id">{s.id}</span>
            <span className="breadcrumb-label">{s.label}</span>
          </button>
        ))}
      </div>

      <div className="section-panel" style={{ marginBottom: "1rem" }}>
        <div className="section-panel-header">
          <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "hsl(var(--primary))", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Principle 5 — Ratio Metrics &amp; Sustainability
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "0.83rem", color: "hsl(215 25% 45%)", lineHeight: 1.6 }}>{helpTexts[activeSection]}</p>
      </div>

      {/* ── 5.1 Cost Structure ── */}
      {activeSection === "5.1" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Cost Structure by Sector — Revenue Allocation (%)</div>
            <div className="chart-card-subtitle">{indexFilter} · Op Cost + Non-Op Cost + Tax + XO + Net Profit = 100% · {intervalFilter}</div>
            <div style={{ height: 300 }}>
              <Bar data={costStructureBySector} options={{ ...barOpts("%"), scales: { x: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { stacked: true, grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}%` } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Effective Tax Rate — ASX 200</div>
            <div className="chart-card-subtitle">Effective tax rate (Tax Cost / PBT) vs Australia statutory 30% rate · 2005–2018</div>
            <div style={{ height: 260 }}>
              <Line data={effectiveTaxRateTimeSeries} options={lineOpts("%")} />
            </div>
          </div>
        </div>
      )}

      {/* ── 5.2 Revenue & EE Growth ── */}
      {activeSection === "5.2" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Revenue Growth by Sector — {intervalFilter}</div>
            <div className="chart-card-subtitle">{indexFilter} · Annualised revenue growth at 1Y, 3Y, 5Y, 10Y intervals</div>
            <div style={{ height: 280 }}>
              <Bar data={revenueGrowthByInterval} options={barOpts("%")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Economic Equity (EE) Growth by Sector</div>
            <div className="chart-card-subtitle">{indexFilter} · EE growth rate 2005–2018 · EE = cumulative (PAT − ECF)</div>
            <div style={{ height: 280 }}>
              <Line data={eeGrowthBySector} options={lineOpts("%")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Revenue Growth vs EE Growth — Correlation Scatter</div>
            <div className="chart-card-subtitle">Sectors that grow revenue tend to also grow EE — but EP ensures capital efficiency</div>
            <div style={{ height: 280 }}>
              <Scatter data={revVsEeGrowthScatter} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { x: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "Revenue Growth % p.a.", font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, title: { display: true, text: "EE Growth % p.a.", font: { size: 10 } } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── 5.3 ROA & Profit Margin ── */}
      {activeSection === "5.3" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Return on Assets (ROA) by Sector — {intervalFilter}</div>
            <div className="chart-card-subtitle">{indexFilter} · ROA = PAT / Calc Assets at 1Y, 3Y, 5Y, 10Y intervals</div>
            <div style={{ height: 280 }}>
              <Bar data={roaBySector} options={barOpts("%")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Profit Margin by Sector — {intervalFilter}</div>
            <div className="chart-card-subtitle">{indexFilter} · Profit Margin = PAT_EX / Revenue · 2005–2018</div>
            <div style={{ height: 280 }}>
              <Line data={profitMarginBySector} options={lineOpts("%")} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Ke-ROE-TER Triangle — {intervalFilter}</div>
            <div className="chart-card-subtitle">Radar showing relative performance across all three financial market metrics · EP vs EPS cohorts</div>
            <div style={{ height: 280 }}>
              <Radar data={keRoeTriangle} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { r: { ticks: { font: { size: 9 } }, grid: { color: "hsl(214 32% 88%)" } } } }} />
            </div>
          </div>
        </div>
      )}

      {/* ── 5.4 Asset Intensity ── */}
      {activeSection === "5.4" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Asset Intensity Ratios by Sector</div>
            <div className="chart-card-subtitle">{indexFilter} · FA Intensity + GW Intensity + OA Intensity — capital structure by sector</div>
            <div style={{ height: 280 }}>
              <Bar data={assetIntensityBySector} options={{ ...barOpts("×"), scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}×` } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">Economic Equity Multiplier — Calc Assets / |EE_open|</div>
            <div className="chart-card-subtitle">{indexFilter} · Higher multiplier = more debt-financed assets · 2005–2018</div>
            <div style={{ height: 280 }}>
              <Line data={econEquityMultiplier} options={{ ...lineOpts("×"), scales: { x: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 } } }, y: { grid: { color: "hsl(214 32% 94%)" }, ticks: { font: { size: 10 }, callback: (v: any) => `${v}×` } } } }} />
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">M:B Ratio Distribution — {intervalFilter}</div>
            <div className="chart-card-subtitle">{indexFilter} · Number of companies in each M:B band across 1Y, 3Y, 5Y, 10Y intervals</div>
            <div style={{ height: 260 }}>
              <Bar data={mbRatioIntervals} options={barOpts("")} />
            </div>
          </div>
        </div>
      )}

      {/* ── 5.5 ESG & Sustainability ── */}
      {activeSection === "5.5" && (
        <div className="charts-grid">
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">ESG &amp; Sustainability Metrics by EP Cohort</div>
            <div className="chart-card-subtitle">6 ESG dimensions · EP Dominant vs Middle vs EPS Dominant · {indexFilter}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
              <div style={{ height: 300 }}>
                <Radar data={esgMetricsData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" as const } }, scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, font: { size: 9 } }, grid: { color: "hsl(214 32% 88%)" }, pointLabels: { font: { size: 10 } } } } }} />
              </div>
              <div style={{ overflowY: "auto", maxHeight: 300 }}>
                <table className="data-table">
                  <thead><tr><th>Metric</th><th>EP Dom.</th><th>Middle</th><th>EPS Dom.</th></tr></thead>
                  <tbody>
                    {esgKpis.map((row: any) => (
                      <tr key={row.metric}>
                        <td style={{ fontWeight: 500 }}>{row.metric}</td>
                        <td style={{ color: "hsl(152 60% 35%)", fontWeight: 600 }}>{row.epDominant}</td>
                        <td style={{ color: "hsl(213 75% 40%)", fontWeight: 500 }}>{row.middle}</td>
                        <td style={{ color: "hsl(0 70% 45%)", fontWeight: 500 }}>{row.epsDominant}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div className="chart-card" style={{ gridColumn: "1 / -1" }}>
            <div className="chart-card-title">CISSA &amp; ESG — Alignment Principle</div>
            <div className="chart-card-subtitle">Companies that create genuine Economic Profit tend to create sustainable, long-term value for all stakeholders</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginTop: "0.5rem" }}>
              {[
                { icon: "🌱", title: "Environmental", text: "EP-dominant companies invest in operational efficiency, reducing waste and emissions as a byproduct of capital discipline.", color: "hsl(152 60% 40%)" },
                { icon: "🤝", title: "Social", text: "Sustainable EP requires customer satisfaction, employee engagement, and community trust — creating aligned incentives.", color: "hsl(213 75% 40%)" },
                { icon: "⚖️", title: "Governance", text: "Long-term EP focus aligns executive incentives with genuine value creation rather than short-term EPS manipulation.", color: "hsl(38 60% 52%)" },
              ].map(({ icon, title, text, color }) => (
                <div key={title} style={{ padding: "1rem", borderRadius: 8, border: `1.5px solid ${color}20`, background: `${color}08` }}>
                  <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>{icon}</div>
                  <div style={{ fontWeight: 700, fontSize: "0.9rem", color, marginBottom: "0.5rem" }}>{title}</div>
                  <p style={{ margin: 0, fontSize: "0.8rem", color: "hsl(215 25% 45%)", lineHeight: 1.5 }}>{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
