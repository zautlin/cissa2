import { useState, useRef, useEffect } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import annotationPlugin from "chartjs-plugin-annotation";

ChartJS.register(
  CategoryScale, LinearScale, LineElement, PointElement,
  Title, Tooltip, Legend, Filler, annotationPlugin
);

// ─── Bow Wave data generator ───────────────────────────────────────────────
// Returns a bell-curve shaped EP stream: rises then falls across 30 periods
function bellCurve(
  years: number[],
  peakYear: number,
  peakValue: number,
  sigma: number
): number[] {
  return years.map(y => {
    const d = y - peakYear;
    return peakValue * Math.exp(-(d * d) / (2 * sigma * sigma));
  });
}

// Each company: { peakValue in $bn, peakOffset (peak relative to T0), sigma }
const COMPANIES: Record<string, {
  label: string;
  baselinePeak: number;
  baselinePeakOffset: number;
  baselineSigma: number;
  newPeak: number;
  newPeakOffset: number;
  newSigma: number;
  wealthCreation: string;
  wealthDirection: "positive" | "negative";
  description: string;
}> = {
  COH: {
    label: "Cochlear (COH)",
    baselinePeak: 0.35, baselinePeakOffset: 3, baselineSigma: 6,
    newPeak: 0.72, newPeakOffset: 5, newSigma: 8,
    wealthCreation: "$3.1b",
    wealthDirection: "positive",
    description: "Cochlear established new EP expectations through sustained product innovation and global expansion, creating substantial long-term shareholder wealth.",
  },
  REA: {
    label: "REA Group (REA)",
    baselinePeak: 0.28, baselinePeakOffset: 2, baselineSigma: 5,
    newPeak: 0.95, newPeakOffset: 6, newSigma: 9,
    wealthCreation: "$8.4b",
    wealthDirection: "positive",
    description: "REA Group's dominant digital property platform drove extraordinary EP growth, far exceeding baseline expectations set at the start of the period.",
  },
  CSL: {
    label: "CSL Limited (CSL)",
    baselinePeak: 0.55, baselinePeakOffset: 4, baselineSigma: 7,
    newPeak: 1.45, newPeakOffset: 6, newSigma: 10,
    wealthCreation: "$12.7b",
    wealthDirection: "positive",
    description: "CSL's biotherapeutics leadership and R&D investment generated one of the largest EP bow wave enhancements of any ASX company.",
  },
  BHP: {
    label: "BHP Group (BHP)",
    baselinePeak: 3.2, baselinePeakOffset: 2, baselineSigma: 5,
    newPeak: 1.8, newPeakOffset: 1, newSigma: 4,
    wealthCreation: "$18.5b",
    wealthDirection: "negative",
    description: "BHP's commodity cycle exposure resulted in EP expectations failing to be met, with declining capital returns destroying significant shareholder wealth.",
  },
  MSFT: {
    label: "Microsoft (MSFT)",
    baselinePeak: 8.5, baselinePeakOffset: 3, baselineSigma: 6,
    newPeak: 18.2, newPeakOffset: 7, newSigma: 12,
    wealthCreation: "$420b",
    wealthDirection: "positive",
    description: "Microsoft's cloud transformation under Satya Nadella drove unprecedented EP bow wave expansion, creating hundreds of billions in new shareholder wealth.",
  },
  IDX: {
    label: "ASX 300 Aggregate",
    baselinePeak: 28.0, baselinePeakOffset: 3, baselineSigma: 6,
    newPeak: 32.5, newPeakOffset: 5, newSigma: 8,
    wealthCreation: "$85b",
    wealthDirection: "positive",
    description: "The ASX 300 aggregate EP bow wave shows moderate aggregate wealth creation, masking wide dispersion between EP-dominant and EPS-dominant companies.",
  },
};

const TABS = [
  { id: "overview", label: "2.1  Overview" },
  { id: "bow-wave", label: "2.2  Bow Wave Concept" },
  { id: "pair", label: "2.3  Pair of EP Bow Waves" },
  { id: "long-term", label: "2.4  Long-Term Focus" },
  { id: "reconcile", label: "2.5  Wealth Reconciliation" },
];

export default function PrincipleTwoPage() {
  const [activeTab, setActiveTab] = useState("pair");
  const [selectedCompany, setSelectedCompany] = useState("COH");
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);

  const company = COMPANIES[selectedCompany];

  // Build year labels: T-10 … T+15 (26 points)
  const T0 = 0; // index 10 = T0
  const yearOffsets = Array.from({ length: 26 }, (_, i) => i - 10);
  const currentYear = 2014;
  const yearLabels = yearOffsets.map(o => {
    const y = currentYear + o;
    return o === 0 ? `${y} (T₀)` : `${y}`;
  });

  // Baseline = starts at T-10, peaks around T0+baselinePeakOffset
  const baselineData = bellCurve(yearOffsets, company.baselinePeakOffset, company.baselinePeak, company.baselineSigma);
  // New expectations = starts near T0, peaks later
  const newData = bellCurve(yearOffsets, company.newPeakOffset, company.newPeak, company.newSigma);
  // mask new wave to only show from T0 (index 10) onwards
  const newDataMasked = newData.map((v, i) => (yearOffsets[i] >= 0 ? v : null));

  const unit = selectedCompany === "MSFT" ? "$bn" : selectedCompany === "IDX" ? "$bn" : "$m";
  const scaleMultiplier = selectedCompany === "MSFT" || selectedCompany === "IDX" ? 1000 : 1;

  const bowWaveData = {
    labels: yearLabels,
    datasets: [
      {
        label: `Baseline EP Expectations (T₀ start)`,
        data: baselineData.map(v => +(v * scaleMultiplier).toFixed(1)),
        borderColor: "hsl(38 70% 48%)",
        backgroundColor: "hsl(38 70% 48% / 0.12)",
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        tension: 0.5,
      },
      {
        label: `New EP Expectations (End of period)`,
        data: (newDataMasked as (number | null)[]).map(v => v !== null ? +(v * scaleMultiplier).toFixed(1) : null),
        borderColor: "hsl(213 75% 40%)",
        backgroundColor: "hsl(213 75% 40% / 0.10)",
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        tension: 0.5,
      },
    ],
  };

  const t0Index = 10; // T0 is at index 10

  const bowWaveOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          boxWidth: 28,
          font: { size: 11 },
          padding: 12,
          usePointStyle: true,
          pointStyle: "line",
        },
      },
      tooltip: {
        callbacks: {
          label: (ctx: any) => {
            const val = ctx.parsed.y;
            if (val === null || val === undefined) return "";
            return ` ${ctx.dataset.label.split("(")[0].trim()}: ${val > 0 ? "+" : ""}${val.toFixed(1)} ${unit}`;
          },
        },
      },
      annotation: {
        annotations: {
          t0Line: {
            type: "line",
            xMin: t0Index,
            xMax: t0Index,
            borderColor: "hsl(220 15% 55%)",
            borderWidth: 1.5,
            borderDash: [5, 4],
            label: {
              content: "T₀ — Measurement Start",
              display: true,
              position: "start",
              font: { size: 10, weight: "600" },
              color: "hsl(220 15% 40%)",
              backgroundColor: "transparent",
              padding: 2,
            },
          },
          wealthLabel: {
            type: "label",
            xValue: t0Index + 6,
            yValue: company.newPeak * scaleMultiplier * 0.55,
            content: [
              company.wealthDirection === "positive"
                ? `▲ ${company.wealthCreation} enhancement`
                : `▼ ${company.wealthCreation} reduction`,
              "to shareholder wealth",
            ],
            font: { size: 10.5, weight: "700" },
            color: company.wealthDirection === "positive" ? "hsl(152 60% 35%)" : "hsl(0 72% 45%)",
            backgroundColor: company.wealthDirection === "positive"
              ? "hsl(152 60% 94%)"
              : "hsl(0 72% 95%)",
            borderColor: company.wealthDirection === "positive"
              ? "hsl(152 60% 70%)"
              : "hsl(0 72% 75%)",
            borderWidth: 1,
            borderRadius: 5,
            padding: { x: 8, y: 5 },
          },
        },
      },
    },
    scales: {
      x: {
        ticks: {
          font: { size: 9 },
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 14,
        },
        grid: { color: "rgba(0,0,0,0.04)" },
      },
      y: {
        title: {
          display: true,
          text: `Economic Profit (EP) — ${unit}`,
          font: { size: 10, weight: "600" },
          color: "hsl(220 15% 45%)",
        },
        ticks: {
          font: { size: 9 },
          callback: (v: number | string) => `${v}`,
        },
        grid: { color: "rgba(0,0,0,0.04)" },
        min: 0,
      },
    },
  };

  return (
    <div style={{ padding: "1.5rem", maxWidth: "1400px" }}>

      {/* Page header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.25rem" }}>
          <div style={{
            width: "28px", height: "28px", borderRadius: "50%",
            background: "hsl(213 75% 22%)", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.75rem", fontWeight: 700, flexShrink: 0,
          }}>2</div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "hsl(var(--primary))", margin: 0 }}>
            Principle 2: A Primary Focus on the Longer Term
          </h1>
        </div>
        <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", marginLeft: "2.125rem", lineHeight: 1.6 }}>
          Market capitalisation reflects the present value of the entire expected EP stream — the EP Bow Wave. Organisations that sustain and grow EP over the long term create the most enduring shareholder wealth.
        </p>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: "0.25rem", borderBottom: "2px solid hsl(var(--border))",
        marginBottom: "1.5rem", overflowX: "auto",
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            data-testid={`tab-p2-${t.id}`}
            style={{
              padding: "0.5rem 0.875rem",
              fontSize: "0.8125rem",
              fontWeight: activeTab === t.id ? 700 : 500,
              color: activeTab === t.id ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
              background: "none",
              border: "none",
              borderBottom: activeTab === t.id ? "2px solid hsl(var(--primary))" : "2px solid transparent",
              marginBottom: "-2px",
              cursor: "pointer",
              whiteSpace: "nowrap",
              transition: "color 150ms",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Pair of EP Bow Waves (HERO) ── */}
      {activeTab === "pair" && (
        <div>
          {/* Hero chart card */}
          <div className="chart-card" style={{
            marginBottom: "1.25rem",
            borderTop: "3px solid hsl(213 75% 22%)",
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <div className="chart-card-title" style={{ fontSize: "1rem", marginBottom: "0.125rem" }}>
                  Pair of EP Bow Waves
                </div>
                <div className="chart-card-subtitle">
                  Baseline expectations (orange) vs. delivered performance + revised expectations (blue) — illustrating wealth creation or destruction
                </div>
              </div>

              {/* Company selector */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", flexShrink: 0 }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 600, color: "hsl(var(--muted-foreground))" }}>
                  Company:
                </label>
                <select
                  value={selectedCompany}
                  onChange={e => setSelectedCompany(e.target.value)}
                  data-testid="select-company"
                  style={{
                    padding: "0.375rem 0.75rem",
                    borderRadius: "0.375rem",
                    border: "1px solid hsl(var(--border))",
                    background: "hsl(var(--background))",
                    color: "hsl(var(--foreground))",
                    fontSize: "0.8125rem",
                    fontWeight: 500,
                    cursor: "pointer",
                    minWidth: "180px",
                  }}
                >
                  {Object.entries(COMPANIES).map(([key, c]) => (
                    <option key={key} value={key}>{c.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Chart */}
            <div style={{ height: "340px" }}>
              <Line data={bowWaveData} options={bowWaveOptions} />
            </div>

            {/* Company narrative */}
            <div style={{
              marginTop: "1rem",
              padding: "0.875rem 1rem",
              background: company.wealthDirection === "positive"
                ? "hsl(152 60% 96%)"
                : "hsl(0 72% 97%)",
              borderLeft: `3px solid ${company.wealthDirection === "positive" ? "hsl(152 60% 40%)" : "hsl(0 72% 51%)"}`,
              borderRadius: "0 0.375rem 0.375rem 0",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <span style={{
                  fontWeight: 700, fontSize: "0.875rem",
                  color: company.wealthDirection === "positive" ? "hsl(152 60% 30%)" : "hsl(0 72% 40%)",
                }}>
                  {company.wealthDirection === "positive" ? "▲" : "▼"} {company.wealthCreation}{" "}
                  {company.wealthDirection === "positive" ? "enhancement" : "reduction"} to shareholder wealth
                </span>
                <span style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>
                  — {company.label}
                </span>
              </div>
              <p style={{ fontSize: "0.8125rem", color: "hsl(var(--muted-foreground))", margin: 0, lineHeight: 1.6 }}>
                {company.description}
              </p>
            </div>
          </div>

          {/* How to read this chart */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
            <div className="chart-card" style={{ borderLeft: "3px solid hsl(38 70% 48%)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <div style={{ width: "28px", height: "3px", background: "hsl(38 70% 48%)", borderRadius: "2px" }} />
                <span style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))" }}>
                  Orange Curve
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
                <strong>Baseline EP Expectations</strong> set at the start of the measurement period (T₀). This represents what the market priced in at the beginning — the EP stream the company was expected to deliver.
              </p>
            </div>

            <div className="chart-card" style={{ borderLeft: "3px solid hsl(213 75% 40%)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <div style={{ width: "28px", height: "3px", background: "hsl(213 75% 40%)", borderRadius: "2px" }} />
                <span style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))" }}>
                  Blue Curve
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
                <strong>New EP Expectations</strong> at the end of the measurement period — the actual delivered performance combined with the revised forward expectation of the EP stream.
              </p>
            </div>

            <div className="chart-card" style={{ borderLeft: "3px solid hsl(var(--primary))" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
                <span style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))" }}>
                  The Gap = Wealth Change
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
                The area between the two curves represents the total change in shareholder wealth. Blue above orange = wealth creation. Orange above blue = wealth destruction. The gap is the present value of the difference in EP expectations.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Overview ── */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
          <div className="chart-card">
            <div className="chart-card-title">Market Value as a Function of EP</div>
            <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {[
                { label: "Book Equity (BV)", value: "Capital invested by shareholders", color: "hsl(213 75% 22%)" },
                { label: "PV of EP Stream", value: "Present value of the expected EP Bow Wave", color: "hsl(38 60% 52%)" },
                { label: "Market Cap", value: "BV + PV(EP) = Enterprise Value", color: "hsl(152 60% 40%)" },
              ].map(item => (
                <div key={item.label} style={{
                  padding: "0.75rem 1rem",
                  background: "hsl(var(--muted))",
                  borderRadius: "0.5rem",
                  borderLeft: `3px solid ${item.color}`,
                }}>
                  <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: item.color, marginBottom: "0.2rem" }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))" }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-card-title">Three Dimensions of the Bow Wave</div>
            <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {[
                { dim: "Height", desc: "Return dimension — how high above Ke is ROE? The peak of the EP curve.", icon: "↕" },
                { dim: "Width", desc: "Size dimension — how large is the equity capital base? Wide base = large absolute EP.", icon: "↔" },
                { dim: "Length", desc: "Sustainability — how far into the future can EP above Ke be maintained?", icon: "→" },
              ].map(d => (
                <div key={d.dim} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
                  <div style={{
                    width: "32px", height: "32px", borderRadius: "0.375rem",
                    background: "hsl(213 75% 22% / 0.1)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "1rem", flexShrink: 0,
                    color: "hsl(213 75% 22%)",
                    fontWeight: 700,
                  }}>{d.icon}</div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))" }}>{d.dim}</div>
                    <div style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>{d.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Bow Wave Concept ── */}
      {activeTab === "bow-wave" && (
        <div className="chart-card">
          <div className="chart-card-title">The EP Bow Wave — Core Concept</div>
          <div className="help-panel" style={{ marginBottom: "1.25rem", marginTop: "0.75rem" }}>
            <p style={{ margin: 0, lineHeight: 1.7, fontSize: "0.8125rem" }}>
              The <strong>EP Bow Wave</strong> is the signature analytical construct of the CISSA platform. A company's EP stream over time traces a characteristic wave shape — rising as the business scales its advantage, peaking when competition or capital constraints bind, then gradually declining as EP mean-reverts toward Ke.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
            {[
              {
                title: "EP = (ROE − Ke) × Book Equity",
                body: "Economic Profit (EP) measures value creation above and beyond the cost of equity. When ROE exceeds Ke, EP is positive; the company creates wealth. When ROE falls below Ke, EP is negative; capital is being destroyed.",
              },
              {
                title: "Market Cap = BV + PV(EP Wave)",
                body: "An investor buying shares today is paying for: (1) the book value of equity already deployed, plus (2) the present value of all future EP — the entire bow wave. This directly links operating performance to market value.",
              },
              {
                title: "The Bell Curve Shape",
                body: "The EP stream typically forms a bell curve: near-zero at the start (early stage), rising as scale and competitive advantage accumulate, peaking, then declining as competition erodes the excess return toward Ke.",
              },
              {
                title: "Why the Long Term Matters",
                body: "Short-term EPS management can temporarily lift reported earnings while eroding the long-term EP wave. CISSA's framework makes this visible: a shrinking bow wave signals long-term wealth destruction even as short-term metrics look healthy.",
              },
            ].map(c => (
              <div key={c.title} style={{
                padding: "1rem",
                background: "hsl(var(--muted))",
                borderRadius: "0.5rem",
              }}>
                <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--primary))", marginBottom: "0.375rem" }}>
                  {c.title}
                </div>
                <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.65, margin: 0 }}>
                  {c.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab: Long-Term Focus ── */}
      {activeTab === "long-term" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
          <div className="chart-card">
            <div className="chart-card-title">How the Pair of Bow Waves Proves Long-Term Focus</div>
            <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              {[
                { step: "1", title: "Establish baseline at T₀", body: "At the start of a period, market cap embeds baseline EP expectations — the orange bow wave. This is observable from M:B ratio and Ke." },
                { step: "2", title: "Measure delivered EP", body: "Over the period, actual EP delivered is calculated from financial data: ROE-Ke × Book Equity, period by period." },
                { step: "3", title: "Calculate new forward expectations", body: "At period end, revised EP expectations are embedded in the new market cap. The blue curve reflects what the market now expects." },
                { step: "4", title: "Measure wealth creation", body: "Wealth created = PV(new wave) − PV(baseline wave). The gap, discounted at Ke, gives a precise dollar measure of value added or destroyed." },
              ].map(s => (
                <div key={s.step} style={{ display: "flex", gap: "0.875rem" }}>
                  <div style={{
                    width: "24px", height: "24px", borderRadius: "50%",
                    background: "hsl(213 75% 22%)", color: "#fff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "0.6875rem", fontWeight: 700, flexShrink: 0,
                    marginTop: "1px",
                  }}>{s.step}</div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.125rem" }}>{s.title}</div>
                    <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>{s.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-card-title">EP Focus vs EPS Focus</div>
            <div style={{ marginTop: "0.75rem" }}>
              <table style={{ width: "100%", fontSize: "0.75rem", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "hsl(var(--muted))" }}>
                    <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 700, color: "hsl(var(--foreground))" }}>Dimension</th>
                    <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 700, color: "hsl(38 60% 45%)" }}>EPS-Dominant</th>
                    <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 700, color: "hsl(213 75% 35%)" }}>EP-Dominant</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Metric", "Earnings per share", "Economic Profit"],
                    ["Capital cost", "Ignored", "Explicitly included"],
                    ["Time horizon", "Next quarter/year", "Full EP wave lifecycle"],
                    ["Value driver", "Short-term EPS growth", "Long-term EP sustainability"],
                    ["TSR (10yr Ann.)", "~5.7% ASX 300", "~14.8% ASX 300"],
                    ["Wealth creation", "Often negative", "Strongly positive"],
                  ].map((row, i) => (
                    <tr key={i} style={{ borderTop: "1px solid hsl(var(--border))" }}>
                      <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600, color: "hsl(var(--foreground))" }}>{row[0]}</td>
                      <td style={{ padding: "0.5rem 0.75rem", color: "hsl(var(--muted-foreground))" }}>{row[1]}</td>
                      <td style={{ padding: "0.5rem 0.75rem", color: "hsl(213 75% 35%)", fontWeight: 500 }}>{row[2]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Wealth Reconciliation ── */}
      {activeTab === "reconcile" && (
        <div className="chart-card">
          <div className="chart-card-title">Reconciling the Bow Wave with Observed Wealth Creation</div>
          <div className="help-panel" style={{ marginTop: "0.75rem", marginBottom: "1.25rem" }}>
            <p style={{ margin: 0, lineHeight: 1.7, fontSize: "0.8125rem" }}>
              The bow wave framework reconciles perfectly with Total Shareholder Return (TSR) adjusted for the cost of equity (Ke). The change in the present value of the EP stream, plus actual EP delivered, equals the wealth created — which in turn equals TSR minus Ke over the period.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
            {[
              {
                formula: "TSR − Ke",
                label: "Excess Shareholder Return",
                body: "The observable return above the cost of equity. If TSR = 18% and Ke = 10%, the excess return is 8% — equivalent to the EP wave shift.",
                color: "hsl(213 75% 22%)",
              },
              {
                formula: "EP Delivered",
                label: "Current Period Value Add",
                body: "The actual EP earned in the period — (ROE−Ke)×Book Equity. This is the realised portion of the bow wave, extracted as value during the period.",
                color: "hsl(38 60% 52%)",
              },
              {
                formula: "ΔPVEP",
                label: "Change in Forward Expectations",
                body: "The shift in the present value of forward EP expectations — the difference between the new blue wave and the original orange wave, discounted at Ke.",
                color: "hsl(152 60% 40%)",
              },
            ].map(f => (
              <div key={f.label} style={{
                padding: "1.25rem",
                background: "hsl(var(--muted))",
                borderRadius: "0.5rem",
                borderTop: `3px solid ${f.color}`,
                textAlign: "center",
              }}>
                <div style={{
                  fontSize: "1.5rem", fontWeight: 800,
                  color: f.color, marginBottom: "0.375rem",
                  fontFamily: "monospace",
                }}>{f.formula}</div>
                <div style={{ fontWeight: 700, fontSize: "0.8125rem", color: "hsl(var(--foreground))", marginBottom: "0.5rem" }}>
                  {f.label}
                </div>
                <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.6, margin: 0 }}>
                  {f.body}
                </p>
              </div>
            ))}
          </div>
          <div style={{
            marginTop: "1.25rem",
            padding: "1rem 1.25rem",
            background: "hsl(213 75% 22% / 0.05)",
            borderRadius: "0.5rem",
            border: "1px solid hsl(213 75% 22% / 0.15)",
            textAlign: "center",
          }}>
            <span style={{ fontSize: "1.125rem", fontWeight: 700, color: "hsl(213 75% 22%)", fontFamily: "monospace" }}>
              Wealth Created = EP Delivered + ΔPVEP = TSR − Ke
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
