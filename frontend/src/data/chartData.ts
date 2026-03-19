// CISSA Platform — chart data (based on slide deck examples)

export const years2001to2024 = Array.from({ length: 24 }, (_, i) => String(2001 + i));
export const years2001to2019 = Array.from({ length: 19 }, (_, i) => String(2001 + i));

// ROE-Ke time series (Economic Profitability by Index) — approximate from slides
export const roeKeByIndex = {
  labels: years2001to2019,
  datasets: [
    {
      label: "LT Average",
      data: Array(19).fill(10.6),
      borderColor: "#94a3b8",
      borderWidth: 1.5,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0,
    },
    {
      label: "1 Year",
      data: [6.7, 6.0, 8.1, 9.2, 9.5, 10.1, 8.8, 8.8, 9.8, 10.9, 10.9, 13.3, 12.4, 11.5, 12.1, 13.9, 13.0, 13.9, 14.8],
      borderColor: "#d4a726",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "3 Years",
      data: [9.0, 9.2, 9.2, 9.2, 8.8, 9.2, 9.2, 9.2, 9.8, 10.8, 11.0, 11.6, 12.1, 12.5, 13.0, 13.5, 13.8, 13.9, 14.1],
      borderColor: "#22c55e",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "5 Years",
      data: [9.2, 9.2, 9.2, 9.5, 9.7, 9.7, 9.4, 9.4, 9.8, 10.1, 10.7, 11.7, 12.0, 12.1, 12.5, 12.9, 13.0, 13.5, 13.9],
      borderColor: "#3b82f6",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "10 Years",
      data: [null, null, null, null, null, null, null, null, null, 9.2, 9.8, 10.1, 10.4, 10.6, 10.7, 11.2, 12.0, 12.5, 12.9],
      borderColor: "#1e293b",
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
  ],
};

// TER-Ke time series (Wealth Creation by Index)
export const terKeByIndex = {
  labels: years2001to2019,
  datasets: [
    {
      label: "1 Year",
      data: [-26.9, -27.7, 3.9, 0.2, -5.8, 2.2, 6.1, -30.9, -0.7, 8.6, 6.8, 8.5, 19.1, 9.3, 3.2, 2.2, 14.5, 6.0, 11.8],
      borderColor: "#d4a726",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "3 Years",
      data: [null, null, -18.4, -9.6, -1.0, -1.3, 0.8, -8.1, -9.0, -10.1, 4.3, 7.4, 10.1, 11.3, 10.4, 4.7, 5.8, 7.2, 10.8],
      borderColor: "#22c55e",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "5 Years",
      data: [null, null, null, null, -13.6, -7.2, 0.7, -5.7, -6.0, -9.1, -5.5, -1.5, -0.3, 0.2, 0.7, 0.1, 0.5, 5.5, 6.8],
      borderColor: "#3b82f6",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "10 Years",
      data: Array(19).fill(null).map((_, i) => i < 9 ? null : [null,null,null,null,null,null,null,null,null,0.2,0.1,0.2,0.3,0.7,0.1,0.5,5.7,6.3,6.8][i]),
      borderColor: "#1e293b",
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
  ],
};

// M:B Ratio time series
export const mbRatioByIndex = {
  labels: years2001to2019,
  datasets: [
    {
      label: "LT Average",
      data: Array(19).fill(3.7),
      borderColor: "#94a3b8",
      borderWidth: 1.5,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0,
    },
    {
      label: "1 Year",
      data: [5.5, 4.0, null, 3.8, 3.6, 3.4, 3.4, 3.2, 2.9, 2.5, 2.6, 2.8, 2.9, 3.3, 3.6, 3.8, 4.0, 4.3, 4.7, 5.1],
      borderColor: "#d4a726",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "3 Years",
      data: [null, null, 4.4, 3.8, 3.6, 3.4, 3.4, 3.2, 2.8, 2.6, 2.6, 2.8, 3.0, 3.3, 3.6, 3.8, 4.0, 4.3, 4.7],
      borderColor: "#22c55e",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "5 Years",
      data: [null, null, null, null, 3.7, 3.6, 3.4, 3.4, 3.1, 2.9, 2.9, 3.1, 3.0, 3.0, 3.1, 3.2, 3.3, 3.5, 3.8],
      borderColor: "#3b82f6",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
    {
      label: "10 Years",
      data: Array(19).fill(null).map((_, i) => i < 9 ? null : [null,null,null,null,null,null,null,null,null,3.4,3.1,3.0,3.0,3.2,3.3,3.5,3.8][i - 9]),
      borderColor: "#1e293b",
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      fill: false,
    },
  ],
};

// ROE-Ke distribution histogram (by industry sector)
export const roeKeDistribution = {
  labels: ["-20","-18","-16","-14","-12","-10","-8","-6","-4","-2","0","2","4","6","8","10","12","14","16","18","20"],
  datasets: [{
    label: "Industry Sectors",
    data: [1, 1, 2, 2, 3, 4, 5, 8, 10, 16, 20, 25, 21, 16, 12, 8, 5, 3, 2, 1, 1],
    backgroundColor: "hsl(213 75% 30% / 0.75)",
    borderColor: "hsl(213 75% 30%)",
    borderWidth: 1,
    borderRadius: 2,
  }],
};

// TER-Ke distribution histogram
export const terKeDistribution = {
  labels: ["-20","-18","-16","-14","-12","-10","-8","-6","-4","-2","0","2","4","6","8","10","12","14","16","18","20"],
  datasets: [{
    label: "Industry Sectors",
    data: [1, 2, 3, 4, 6, 10, 15, 30, 47, 50, 49, 35, 15, 8, 4, 3, 2, 1, 1, 0, 0],
    backgroundColor: "hsl(188 78% 35% / 0.75)",
    borderColor: "hsl(188 78% 35%)",
    borderWidth: 1,
    borderRadius: 2,
  }],
};

// EP Dominant vs EPS Dominant comparison
export const epVsEpsCohorts = {
  labels: ["EPS Growth", "Growth in Book\nEquity per Share", "EP per Share\nGrowth", "Annualised TSR"],
  datasets: [
    {
      label: "EP Dominant (39 cos.)",
      data: [37.8, 7.3, 55.2, 14.8],
      backgroundColor: "hsl(213 75% 22% / 0.85)",
      borderRadius: 3,
    },
    {
      label: "Middle Group (89 cos.)",
      data: [0.6, 1.3, -1.2, 7.4],
      backgroundColor: "hsl(213 75% 45% / 0.75)",
      borderRadius: 3,
    },
    {
      label: "EPS Dominant (152 cos.)",
      data: [3.0, 7.0, -34.0, 5.7],
      backgroundColor: "hsl(213 75% 65% / 0.6)",
      borderRadius: 3,
    },
  ],
};

// ─── EEAI / EEA Index chart (slide 41) ────────────────────────────────────
// Dual-line: "Required to Justify Share Price" vs "Historical Average (Rolling 3Y)"
// with EEA Index count bar at bottom
export const eeaiYears = ["2001","2002","2003","2004","2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"];
export const eeaiRequired = {
  labels: eeaiYears,
  datasets: [
    {
      label: "Required to Justify Share Price",
      data: [8.2, 7.9, 8.5, 9.1, 9.8, 10.2, 9.6, 7.1, 7.8, 9.0, 8.8, 9.3, 9.7, 10.1, 10.4, 10.2, 10.8, 11.2],
      borderColor: "hsl(213 75% 22%)",
      backgroundColor: "hsl(213 75% 22% / 0.1)",
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.35,
      fill: false,
    },
    {
      label: "Historical Average (Rolling 3Y)",
      data: [10.1, 9.8, 9.6, 9.8, 10.0, 10.3, 10.6, 10.2, 9.4, 9.8, 10.2, 10.6, 10.9, 11.1, 11.4, 11.5, 11.7, 12.0],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "hsl(38 60% 52% / 0.08)",
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 3,
      pointHoverRadius: 5,
      tension: 0.35,
      fill: false,
    },
  ],
};

// EEA Index count (companies in index each year)
export const eeaiIndexCount = {
  labels: eeaiYears,
  datasets: [{
    label: "Companies in EEA Index",
    data: [71, 71, 87, 94, 90, 86, 85, 105, 106, 99, 95, 86, 81, 76, 79, 76, 70, 76],
    backgroundColor: "hsl(213 75% 40% / 0.6)",
    borderColor: "hsl(213 75% 30%)",
    borderWidth: 1,
    borderRadius: 2,
  }],
};

// ─── EP Dominant vs EPS Dominant — 4-quadrant scatter (slides 40-41) ────────
export const epDominantScatter = {
  datasets: [
    {
      label: "EP Dominant",
      data: [
        { x: 12, y: 42 }, { x: 18, y: 58 }, { x: 22, y: 71 }, { x: 8, y: 35 },
        { x: 15, y: 50 }, { x: 25, y: 65 }, { x: 10, y: 45 }, { x: 30, y: 80 },
        { x: 5, y: 30 }, { x: 20, y: 55 }, { x: 28, y: 75 }, { x: 14, y: 48 },
      ],
      backgroundColor: "hsl(152 60% 40% / 0.75)",
      borderColor: "hsl(152 60% 30%)",
      pointRadius: 7,
      pointHoverRadius: 9,
    },
    {
      label: "EPS Dominant",
      data: [
        { x: 18, y: -25 }, { x: 22, y: -38 }, { x: 8, y: -12 }, { x: 30, y: -50 },
        { x: 12, y: -20 }, { x: 25, y: -42 }, { x: 5, y: -8 }, { x: 35, y: -60 },
        { x: 15, y: -30 }, { x: 20, y: -35 },
      ],
      backgroundColor: "hsl(0 72% 51% / 0.7)",
      borderColor: "hsl(0 72% 40%)",
      pointRadius: 7,
      pointHoverRadius: 9,
    },
    {
      label: "Mixed / Middle",
      data: [
        { x: 5, y: 8 }, { x: 10, y: 12 }, { x: -5, y: -8 }, { x: 8, y: -5 },
        { x: -8, y: 10 }, { x: 3, y: 5 }, { x: -3, y: -5 }, { x: 0, y: 15 },
        { x: 12, y: -8 }, { x: -10, y: 5 }, { x: 6, y: -2 }, { x: -6, y: 12 },
      ],
      backgroundColor: "hsl(38 60% 52% / 0.65)",
      borderColor: "hsl(38 60% 40%)",
      pointRadius: 6,
      pointHoverRadius: 8,
    },
    {
      label: "Poor Performers",
      data: [
        { x: -12, y: -20 }, { x: -18, y: -35 }, { x: -8, y: -15 }, { x: -25, y: -45 },
        { x: -15, y: -28 }, { x: -5, y: -10 }, { x: -20, y: -38 },
      ],
      backgroundColor: "hsl(220 15% 55% / 0.6)",
      borderColor: "hsl(220 15% 40%)",
      pointRadius: 6,
      pointHoverRadius: 8,
    },
  ],
};

// ─── M:B Ratio distribution histograms (slide 22) ──────────────────────────
export const mbRatioSectorDist = {
  labels: ["<0.5","0.5-1","1-1.5","1.5-2","2-2.5","2.5-3","3-3.5","3.5-4","4-5",">5"],
  datasets: [{
    label: "Sectors (ASX 300)",
    data: [2, 4, 8, 14, 18, 15, 12, 9, 6, 4],
    backgroundColor: "hsl(213 75% 30% / 0.75)",
    borderColor: "hsl(213 75% 22%)",
    borderWidth: 1,
    borderRadius: 3,
  }],
};

export const mbRatioCompanyDist = {
  labels: ["<0.5","0.5-1","1-1.5","1.5-2","2-2.5","2.5-3","3-3.5","3.5-4","4-5",">5"],
  datasets: [
    {
      label: "Materials",
      data: [3, 6, 12, 18, 14, 10, 7, 4, 2, 1],
      backgroundColor: "hsl(38 60% 52% / 0.75)",
      borderRadius: 2,
      borderWidth: 0,
    },
    {
      label: "Financials",
      data: [1, 3, 8, 15, 20, 18, 12, 8, 5, 3],
      backgroundColor: "hsl(213 75% 35% / 0.75)",
      borderRadius: 2,
      borderWidth: 0,
    },
    {
      label: "Healthcare",
      data: [0, 1, 3, 7, 12, 16, 15, 12, 10, 8],
      backgroundColor: "hsl(152 60% 40% / 0.75)",
      borderRadius: 2,
      borderWidth: 0,
    },
  ],
};

// ─── TER-Ke International Comparison (slides 48-52) ─────────────────────────
// 3-panel: USA, UK, Australia — TER-Ke and TER Alpha
export const terIntlYears = ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"];

export const terIntlUSA = {
  labels: terIntlYears,
  datasets: [
    {
      label: "TER-Ke (USA)",
      data: [3.2, 5.8, 2.1, -18.5, -8.2, 6.4, 2.8, 9.1, 12.4, 8.7, 4.2, 6.8, 11.2, 5.9],
      borderColor: "hsl(213 75% 35%)",
      backgroundColor: "hsl(213 75% 35% / 0.1)",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    },
    {
      label: "TER Alpha (USA)",
      data: [1.8, 3.2, 0.8, -9.5, -3.1, 4.2, 1.5, 6.8, 9.1, 6.2, 2.8, 4.5, 8.7, 3.4],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    },
  ],
};

export const terIntlUK = {
  labels: terIntlYears,
  datasets: [
    {
      label: "TER-Ke (UK)",
      data: [2.1, 4.5, 1.2, -22.1, -10.5, 4.8, 1.2, 7.4, 9.8, 5.5, 2.1, 4.2, 8.1, 3.2],
      borderColor: "hsl(213 75% 35%)",
      backgroundColor: "hsl(213 75% 35% / 0.1)",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    },
    {
      label: "TER Alpha (UK)",
      data: [0.8, 2.1, -0.5, -11.2, -4.8, 2.8, 0.2, 4.9, 6.5, 3.1, 0.5, 2.1, 5.4, 1.2],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    },
  ],
};

export const terIntlAUS = {
  labels: terIntlYears,
  datasets: [
    {
      label: "TER-Ke (Australia)",
      data: [-5.8, 2.2, 6.1, -30.9, -0.7, 8.6, 6.8, 8.5, 19.1, 9.3, 3.2, 2.2, 14.5, 6.0],
      borderColor: "hsl(213 75% 35%)",
      backgroundColor: "hsl(213 75% 35% / 0.1)",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    },
    {
      label: "TER Alpha (Australia)",
      data: [-3.1, 1.0, 4.2, -15.5, 0.8, 5.5, 4.1, 6.2, 14.8, 7.1, 1.5, 0.8, 11.2, 3.8],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    },
  ],
};

// Wealth creation decomposition
export const wealthCreationDecomp = {
  labels: ["TSR-Ke (Observed\nWealth Creation)", "Intrinsic\nWealth Creation", "Sustainable Intrinsic\nWealth Creation", "Wealth\nAppropriation"],
  datasets: [{
    label: "Components (%)",
    data: [8.2, 5.4, 3.8, 2.8],
    backgroundColor: [
      "hsl(213 75% 22% / 0.85)",
      "hsl(38 60% 52% / 0.85)",
      "hsl(152 60% 40% / 0.85)",
      "hsl(0 72% 51% / 0.7)",
    ],
    borderRadius: 4,
  }],
};
