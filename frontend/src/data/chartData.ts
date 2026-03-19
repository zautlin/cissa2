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

// ─── EP per Share Growth time series (Section 1.3) ─────────────────────────
export const epPerShareGrowth = {
  labels: ["2001","2002","2003","2004","2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018","2019"],
  datasets: [
    {
      label: "EP per Share Growth (EP Dominant)",
      data: [12.1, 8.5, 18.3, 24.6, 38.2, 45.1, 52.8, 38.9, 22.4, 40.7, 48.3, 55.2, 58.1, 62.4, 55.8, 49.2, 52.7, 55.2, 57.8],
      borderColor: "hsl(152 60% 40%)",
      backgroundColor: "hsl(152 60% 40% / 0.08)",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: true,
    },
    {
      label: "EPS Growth (EP Dominant)",
      data: [10.2, 6.1, 14.8, 19.3, 29.4, 34.8, 39.2, 28.1, 16.5, 30.2, 36.4, 37.8, 41.2, 44.8, 38.5, 34.2, 37.1, 37.8, 39.2],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    },
    {
      label: "EP per Share Growth (EPS Dominant)",
      data: [-5.2, -8.1, -2.4, -3.8, -12.4, -18.6, -22.1, -28.4, -32.1, -34.8, -36.2, -34.0, -33.8, -35.2, -36.8, -34.5, -33.2, -34.0, -35.5],
      borderColor: "hsl(0 72% 51%)",
      backgroundColor: "hsl(0 72% 51% / 0.06)",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    },
  ],
};

// ─── EP per Share by Sector time series (Section 1.3 drill-down) ────────────
export const epPerShareBySector = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018","2019"],
  datasets: [
    {
      label: "Healthcare",
      data: [18.2, 22.4, 28.1, 20.5, 15.8, 24.6, 30.2, 38.5, 42.8, 48.2, 44.5, 40.8, 46.2, 52.4, 56.8],
      borderColor: "hsl(152 60% 40%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
    },
    {
      label: "Technology",
      data: [8.4, 12.8, 18.5, 5.2, 8.4, 22.8, 28.4, 34.2, 40.8, 48.6, 52.4, 58.8, 64.2, 70.5, 76.8],
      borderColor: "hsl(213 75% 40%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
    },
    {
      label: "Consumer Staples",
      data: [5.8, 8.2, 10.4, 6.8, 4.2, 8.8, 12.4, 15.8, 18.2, 20.4, 18.8, 16.2, 18.4, 20.8, 22.4],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
    },
    {
      label: "Materials",
      data: [22.8, 28.4, 32.1, -8.4, -12.8, 8.4, 5.2, -2.4, -4.8, -8.2, -10.4, -12.8, -8.4, -5.2, -4.8],
      borderColor: "hsl(0 72% 51%)",
      backgroundColor: "transparent",
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
    },
  ],
};

// ─── EP Heatmap data (companies × sectors × EP magnitude) ──────────────────
// Represented as a grid: rows = sectors, cols = years, values = EP score
export const epHeatmapData = {
  sectors: ["Healthcare", "Technology", "Consumer Staples", "Financials", "Energy", "Materials", "Utilities", "Industrials"],
  years: ["2010","2011","2012","2013","2014","2015","2016","2017","2018","2019"],
  // Value: EP score normalised -3 to +3 (negative = EP destruction, positive = EP creation)
  values: [
    [1.8, 2.1, 2.4, 2.6, 2.8, 2.5, 2.2, 2.6, 2.9, 3.0],   // Healthcare
    [0.8, 1.2, 1.6, 2.0, 2.4, 2.8, 3.0, 2.8, 2.6, 2.5],   // Technology
    [1.2, 1.4, 1.5, 1.6, 1.7, 1.5, 1.4, 1.5, 1.6, 1.7],   // Consumer Staples
    [0.6, 0.8, 1.0, 1.2, 1.0, 0.8, 0.9, 1.1, 1.3, 1.4],   // Financials
    [1.5, 0.8, 0.4, -0.2, -0.8, -1.5, -0.8, 0.2, 0.5, 0.4], // Energy
    [2.2, 1.8, 0.8, -0.4, -1.2, -1.8, -1.5, -0.8, -0.4, -0.6], // Materials
    [-0.4, -0.2, 0.1, 0.2, 0.3, 0.1, -0.1, 0.1, 0.2, 0.3], // Utilities
    [0.4, 0.6, 0.8, 1.0, 1.2, 1.0, 0.8, 1.0, 1.2, 1.4],   // Industrials
  ],
};

// ─── TSR-Ke vs ROE-Ke scatter (Principle 1 capital market predictor) ─────────
export const tsrKeVsRoeKeScatter = {
  datasets: [
    {
      label: "EP Dominant (High ROE-Ke → High TSR-Ke)",
      data: [
        { x: 8.2, y: 12.4 }, { x: 12.5, y: 18.6 }, { x: 15.8, y: 22.4 },
        { x: 9.4, y: 14.8 }, { x: 18.2, y: 25.6 }, { x: 22.4, y: 28.4 },
        { x: 11.8, y: 16.8 }, { x: 25.2, y: 32.4 }, { x: 6.8, y: 10.2 },
        { x: 19.6, y: 24.8 }, { x: 28.4, y: 35.2 }, { x: 14.2, y: 19.4 },
      ],
      backgroundColor: "hsl(152 60% 40% / 0.75)",
      borderColor: "hsl(152 60% 30%)",
      pointRadius: 7,
      pointHoverRadius: 9,
    },
    {
      label: "EPS Dominant (Low ROE-Ke → Low TSR-Ke)",
      data: [
        { x: 2.8, y: 1.2 }, { x: 5.4, y: 2.8 }, { x: -1.2, y: -3.4 },
        { x: 3.8, y: 0.8 }, { x: 8.4, y: 3.2 }, { x: -3.4, y: -5.8 },
        { x: 1.2, y: -1.4 }, { x: 6.8, y: 4.2 }, { x: -2.4, y: -4.8 },
        { x: 4.2, y: 1.8 }, { x: -4.8, y: -8.2 }, { x: 0.8, y: -2.1 },
      ],
      backgroundColor: "hsl(0 72% 51% / 0.7)",
      borderColor: "hsl(0 72% 40%)",
      pointRadius: 7,
      pointHoverRadius: 9,
    },
    {
      label: "Middle Group",
      data: [
        { x: 4.2, y: 5.8 }, { x: 6.8, y: 7.4 }, { x: 2.4, y: 4.2 },
        { x: 7.8, y: 9.2 }, { x: 3.6, y: 5.0 }, { x: 5.8, y: 6.8 },
        { x: 1.8, y: 3.4 }, { x: 8.4, y: 10.2 }, { x: 4.8, y: 6.2 },
      ],
      backgroundColor: "hsl(38 60% 52% / 0.65)",
      borderColor: "hsl(38 60% 40%)",
      pointRadius: 6,
      pointHoverRadius: 8,
    },
  ],
};

// ─── Wealth Creation Waterfall (decomposition: proper cascade) ────────────────
// Labels + values for a cascade waterfall: each step shows component
export const wealthWaterfallData = {
  labels: [
    "Starting\\nMarket Cap",
    "EP Delivered",
    "ΔPVEP\\n(Revised Fwd)",
    "Risk Premium\\nChange",
    "Ke Change\\nEffect",
    "Total\\nWealth Created",
  ],
  values: [100, 8.2, 5.4, 1.8, -0.8, 114.6],          // abs values (base=100)
  types:  ["base", "pos",  "pos",  "pos", "neg",  "total"],// base|pos|neg|total
  colors: [
    "hsl(213 75% 22% / 0.8)",     // base
    "hsl(152 60% 40% / 0.85)",    // pos
    "hsl(152 60% 40% / 0.85)",    // pos
    "hsl(38 60% 52% / 0.85)",     // pos smaller
    "hsl(0 72% 51% / 0.8)",       // neg
    "hsl(213 75% 40% / 0.9)",     // total
  ],
};

// ─── CISSA Index 2D Scatter (Alignment vs EP Growth) ─────────────────────────
// X = Alignment with CISSA Principles (0-10), Y = EP Growth (%)
export const cissaIndex2DScatter = {
  datasets: [
    {
      label: "ASX 300 — High Alignment",
      data: [
        { x: 8.2, y: 42, label: "COH" }, { x: 9.1, y: 55, label: "CSL" },
        { x: 7.8, y: 38, label: "REA" }, { x: 8.8, y: 48, label: "WTC" },
        { x: 9.4, y: 62, label: "ALU" }, { x: 7.5, y: 35, label: "XRO" },
        { x: 8.5, y: 52, label: "TNE" }, { x: 9.0, y: 58, label: "PME" },
      ],
      backgroundColor: "hsl(152 60% 40% / 0.8)",
      borderColor: "hsl(152 60% 28%)",
      pointRadius: 10,
      pointHoverRadius: 12,
    },
    {
      label: "ASX 300 — Moderate Alignment",
      data: [
        { x: 5.2, y: 18, label: "WBC" }, { x: 6.4, y: 22, label: "CBA" },
        { x: 4.8, y: 12, label: "ANZ" }, { x: 5.8, y: 20, label: "NAB" },
        { x: 6.2, y: 15, label: "WES" }, { x: 5.0, y: 10, label: "WOW" },
        { x: 6.8, y: 28, label: "TLS" }, { x: 4.5, y: 8, label: "AGL" },
      ],
      backgroundColor: "hsl(38 60% 52% / 0.75)",
      borderColor: "hsl(38 60% 38%)",
      pointRadius: 8,
      pointHoverRadius: 10,
    },
    {
      label: "ASX 300 — Low Alignment",
      data: [
        { x: 2.4, y: -18, label: "BHP" }, { x: 3.2, y: -8, label: "RIO" },
        { x: 1.8, y: -24, label: "FMG" }, { x: 2.8, y: -12, label: "NCM" },
        { x: 3.5, y: -5, label: "ORG" }, { x: 2.1, y: -20, label: "WPL" },
      ],
      backgroundColor: "hsl(0 72% 51% / 0.7)",
      borderColor: "hsl(0 72% 38%)",
      pointRadius: 8,
      pointHoverRadius: 10,
    },
  ],
};

// ─── ESG / Sustainability Metrics Panel ────────────────────────────────────
export const esgMetricsData = {
  // Radar chart data: 6 ESG dimensions for 3 cohorts
  labels: ["Carbon Intensity", "Board Diversity", "Exec Pay Alignment", "Supply Chain Governance", "Customer Outcomes", "Long-Term Focus (EP)"],
  datasets: [
    {
      label: "EP Dominant (Top Quartile)",
      data: [72, 78, 82, 74, 86, 90],
      borderColor: "hsl(152 60% 40%)",
      backgroundColor: "hsl(152 60% 40% / 0.12)",
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: "hsl(152 60% 40%)",
    },
    {
      label: "Middle Quartiles",
      data: [55, 58, 52, 50, 62, 55],
      borderColor: "hsl(38 60% 52%)",
      backgroundColor: "hsl(38 60% 52% / 0.08)",
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: "hsl(38 60% 52%)",
    },
    {
      label: "EPS Dominant (Bottom Quartile)",
      data: [38, 42, 35, 32, 44, 28],
      borderColor: "hsl(0 72% 51%)",
      backgroundColor: "hsl(0 72% 51% / 0.08)",
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: "hsl(0 72% 51%)",
    },
  ],
};

// ESG KPIs summary table data
export const esgKpis = [
  { metric: "Carbon Intensity (tCO₂/$M revenue)", epDominant: "42.8", middle: "68.4", epsDominant: "112.6", unit: "tCO₂/$M" },
  { metric: "Board Gender Diversity", epDominant: "38%", middle: "28%", epsDominant: "18%", unit: "%" },
  { metric: "Exec Pay Linked to EP Outcomes", epDominant: "74%", middle: "45%", epsDominant: "22%", unit: "%" },
  { metric: "Supply Chain Sustainability Score", epDominant: "7.4/10", middle: "5.0/10", epsDominant: "3.2/10", unit: "/10" },
  { metric: "Customer Satisfaction Score (NPS)", epDominant: "62", middle: "44", epsDominant: "32", unit: "" },
  { metric: "10yr Ann. TSR-Ke", epDominant: "14.8%", middle: "7.4%", epsDominant: "5.7%", unit: "%" },
];

// ─── All exportable metrics catalogue (for Download page) ────────────────────
export const exportableMetrics = [
  {
    id: "roe_ke_by_index",
    name: "ROE-Ke by Index (Time Series)",
    description: "Economic Profitability — annual, 3Y, 5Y, 10Y rolling averages",
    principle: "Principle 1",
    section: "1.1",
    rows: 19,
    format: ["CSV", "JSON"],
  },
  {
    id: "ter_ke_by_index",
    name: "TER-Ke Wealth Creation by Index",
    description: "Annualised wealth creation measure, all rolling windows",
    principle: "Principle 1",
    section: "1.1",
    rows: 19,
    format: ["CSV", "JSON"],
  },
  {
    id: "mb_ratio_by_index",
    name: "M:B Ratio by Index (Time Series)",
    description: "Market-to-Book ratio across ASX 300 by rolling period",
    principle: "Principle 1",
    section: "1.2",
    rows: 19,
    format: ["CSV", "JSON"],
  },
  {
    id: "roe_ke_distribution",
    name: "ROE-Ke Distribution by Sector",
    description: "Histogram distribution of economic profitability across sectors",
    principle: "Principle 1",
    section: "1.1",
    rows: 21,
    format: ["CSV", "JSON"],
  },
  {
    id: "ep_vs_eps_cohorts",
    name: "EP Dominant vs EPS Dominant Cohort Performance",
    description: "Comparative metrics: EPS Growth, EP/Share Growth, Ann. TSR",
    principle: "Principle 1",
    section: "1.4",
    rows: 3,
    format: ["CSV", "JSON"],
  },
  {
    id: "ep_per_share_growth",
    name: "EP per Share Growth by Cohort",
    description: "EP Dominant vs EPS Dominant EP/Share growth time series",
    principle: "Principle 1",
    section: "1.3",
    rows: 19,
    format: ["CSV", "JSON"],
  },
  {
    id: "ep_per_share_by_sector",
    name: "EP per Share by Sector",
    description: "Sector-level EP per share growth time series (Healthcare, Tech, etc.)",
    principle: "Principle 1",
    section: "1.3",
    rows: 15,
    format: ["CSV", "JSON"],
  },
  {
    id: "ep_heatmap",
    name: "EP Heatmap by Sector × Year",
    description: "EP score grid: 8 sectors × 10 years, normalised to [-3, +3]",
    principle: "Principle 1",
    section: "1.3",
    rows: 80,
    format: ["CSV", "JSON"],
  },
  {
    id: "eeai_required",
    name: "EEA Index — Required ROE-Ke vs Historical",
    description: "Comparison of required EP to justify share price vs rolling historical average",
    principle: "Principle 1",
    section: "1.4",
    rows: 18,
    format: ["CSV", "JSON"],
  },
  {
    id: "ter_intl_comparison",
    name: "TER-Ke International Comparison",
    description: "TER-Ke and TER Alpha for USA, UK, Australia (2005–2018)",
    principle: "Principle 1",
    section: "1.5",
    rows: 42,
    format: ["CSV", "JSON"],
  },
  {
    id: "bow_wave_companies",
    name: "Bow Wave Analysis — Company Data",
    description: "Baseline vs new EP expectations, wealth creation delta per company",
    principle: "Principle 2",
    section: "2.3",
    rows: 6,
    format: ["CSV", "JSON"],
  },
  {
    id: "wealth_waterfall",
    name: "Wealth Creation Decomposition Waterfall",
    description: "EP Delivered + ΔPVEP + Risk Premium Change components",
    principle: "Principle 2",
    section: "2.5",
    rows: 6,
    format: ["CSV", "JSON"],
  },
  {
    id: "cissa_index_2d",
    name: "CISSA Index 2D — Alignment vs EP Growth",
    description: "Company scatter: CISSA Principle Alignment score vs EP Growth %",
    principle: "All Principles",
    section: "Outputs",
    rows: 22,
    format: ["CSV", "JSON"],
  },
  {
    id: "esg_metrics",
    name: "ESG / Sustainability Metrics by Cohort",
    description: "6 ESG dimensions × 3 EP cohorts — Carbon, Diversity, Governance, etc.",
    principle: "Principle 4",
    section: "ESG",
    rows: 6,
    format: ["CSV", "JSON"],
  },
  {
    id: "mb_ratio_distribution",
    name: "M:B Ratio Distribution by Sector",
    description: "Company distribution across M:B bands by sector (Materials, Financials, Healthcare)",
    principle: "Principle 1",
    section: "1.2",
    rows: 30,
    format: ["CSV", "JSON"],
  },
];

// ═══════════════════════════════════════════════════════════════════════
// ADDITIONAL CHARTS FROM ORIGINAL SOURCE — FULL METRICS CATALOGUE
// Sources: formulas.md, aggregators.py, LEGACY_METRICS_COMPLETE.md,
//          all backend services (beta, ke, fv_ecf, ter, ep_growth, etc.)
// ═══════════════════════════════════════════════════════════════════════

// ── Beta Distribution across ASX 300 ──────────────────────────────────
export const betaDistribution = {
  labels: ["0.3","0.4","0.5","0.6","0.7","0.8","0.9","1.0","1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8","1.9","2.0"],
  datasets: [{
    label: "Number of Companies",
    data: [4, 7, 13, 22, 31, 48, 62, 78, 71, 55, 38, 22, 14, 9, 6, 4, 2, 1],
    backgroundColor: "hsl(213 75% 40% / 0.75)",
    borderColor: "hsl(213 75% 22%)",
    borderWidth: 1,
  }]
};

// ── Beta Time Series (Sector Averages) ────────────────────────────────
export const betaTimeSeries = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Materials", data: [1.1,1.2,1.3,1.5,1.4,1.2,1.1,1.0,1.0,0.9,1.0,1.1,1.0,1.1], borderColor: "#b45309", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Financials", data: [1.0,1.1,1.1,1.3,1.2,1.1,1.0,0.9,0.9,0.9,0.9,0.9,0.9,0.9], borderColor: "#1d4ed8", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Healthcare", data: [0.6,0.7,0.7,0.8,0.7,0.7,0.6,0.6,0.6,0.6,0.7,0.7,0.7,0.7], borderColor: "#15803d", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Technology", data: [1.2,1.3,1.4,1.6,1.5,1.4,1.3,1.3,1.2,1.2,1.3,1.4,1.4,1.3], borderColor: "#7c3aed", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Energy", data: [0.9,1.0,1.1,1.4,1.3,1.1,1.0,1.0,1.0,0.9,1.0,1.0,1.0,1.0], borderColor: "#dc2626", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "ASX 200", data: [1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0], borderColor: "#6b7280", backgroundColor: "transparent", tension: 0.3, borderWidth: 2, borderDash: [4,4] },
  ]
};

// ── Cost of Equity (Ke) Decomposition: Rf + Beta×ERP ─────────────────
export const keDecompositionData = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Risk Free Rate (Rf)", data: [5.4,5.7,6.1,5.8,4.2,5.1,4.9,3.5,3.2,2.8,2.4,2.0,2.3,2.5], backgroundColor: "hsl(213 75% 55% / 0.85)", stack: "ke" },
    { label: "Beta × MRP", data: [5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0], backgroundColor: "hsl(38 60% 55% / 0.85)", stack: "ke" },
    { label: "Ke (Total)", type: "line" as const, data: [10.4,10.7,11.1,10.8,9.2,10.1,9.9,8.5,8.2,7.8,7.4,7.0,7.3,7.5], borderColor: "hsl(213 75% 22%)", backgroundColor: "transparent", tension: 0.3, borderWidth: 2.5, pointRadius: 3 } as any,
  ]
};

// ── Ke vs ROE vs TSR Triangle (Radar) ─────────────────────────────────
export const keRoeTriangle = {
  labels: ["Ke (Cost of Equity)", "ROE (Accounting Return)", "TER (Equity Return)", "ROE-Ke (EP%)", "TER-Ke (Wealth Creation)", "TSR (Capital Market)"],
  datasets: [
    { label: "EP Dominant Companies", data: [8.2, 14.5, 13.8, 6.3, 5.6, 12.4], backgroundColor: "hsl(152 60% 40% / 0.2)", borderColor: "hsl(152 60% 40%)", borderWidth: 2, pointRadius: 4 },
    { label: "EPS Dominant Companies", data: [8.2, 9.4, 8.1, 1.2, -0.1, 7.8], backgroundColor: "hsl(0 70% 50% / 0.2)", borderColor: "hsl(0 70% 50%)", borderWidth: 2, pointRadius: 4 },
    { label: "Market Average", data: [8.2, 11.2, 10.5, 3.0, 2.3, 9.8], backgroundColor: "hsl(213 75% 40% / 0.2)", borderColor: "hsl(213 75% 40%)", borderWidth: 2, pointRadius: 4 },
  ]
};

// ── Cost Structure Breakdown (stacked bar per sector) ─────────────────
export const costStructureBySector = {
  labels: ["Materials", "Financials", "Healthcare", "Technology", "Energy", "Consumer Staples", "Utilities", "Industrials"],
  datasets: [
    { label: "Op Cost Margin", data: [65, 42, 58, 52, 72, 78, 55, 68], backgroundColor: "hsl(213 75% 40% / 0.85)", stack: "cost" },
    { label: "Non-Op Cost Margin", data: [8, 22, 10, 12, 9, 7, 18, 10], backgroundColor: "hsl(38 60% 52% / 0.85)", stack: "cost" },
    { label: "Tax Cost Margin", data: [7, 8, 9, 8, 6, 7, 8, 7], backgroundColor: "hsl(152 60% 40% / 0.85)", stack: "cost" },
    { label: "XO Cost Margin", data: [2, 3, 2, 3, 4, 2, 2, 2], backgroundColor: "hsl(0 70% 50% / 0.85)", stack: "cost" },
    { label: "Net Profit Margin", data: [18, 25, 21, 25, 9, 6, 17, 13], backgroundColor: "hsl(213 75% 22% / 0.85)", stack: "cost" },
  ]
};

// ── Revenue Growth by Sector (1Y, 3Y, 5Y, 10Y Annualised) ─────────────
export const revenueGrowthByInterval = {
  labels: ["Materials", "Financials", "Healthcare", "Technology", "Energy", "Consumer Staples", "Utilities"],
  datasets: [
    { label: "1Y Growth", data: [4.2, 3.8, 8.5, 12.4, 2.1, 3.5, 1.8], backgroundColor: "hsl(213 75% 70% / 0.8)" },
    { label: "3Y Annualised", data: [5.1, 4.2, 9.8, 14.2, 3.4, 4.1, 2.2], backgroundColor: "hsl(213 75% 50% / 0.8)" },
    { label: "5Y Annualised", data: [4.8, 5.5, 11.2, 15.8, 2.8, 4.8, 2.5], backgroundColor: "hsl(213 75% 35% / 0.8)" },
    { label: "10Y Annualised", data: [6.2, 6.1, 12.5, 13.1, 3.2, 5.1, 2.8], backgroundColor: "hsl(213 75% 22% / 0.8)" },
  ]
};

// ── Economic Equity (EE) Growth by Sector ─────────────────────────────
export const eeGrowthBySector = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Materials", data: [8.2,9.1,11.3,7.2,4.1,7.8,6.2,5.4,4.8,4.2,3.9,4.1,4.5,4.8], borderColor: "#b45309", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Financials", data: [10.1,11.2,12.4,5.8,6.2,8.4,7.8,8.1,9.2,8.8,9.4,9.8,10.1,9.5], borderColor: "#1d4ed8", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Healthcare", data: [12.4,13.8,14.2,12.1,11.8,14.5,15.2,14.8,15.4,16.2,14.8,15.1,14.2,13.8], borderColor: "#15803d", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Technology", data: [15.2,17.4,18.1,12.4,10.1,18.4,19.2,20.1,22.4,24.8,21.2,23.4,25.1,22.8], borderColor: "#7c3aed", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "ASX 200 Avg", data: [9.5,10.2,11.8,7.5,6.8,9.8,9.2,9.8,10.4,10.8,9.5,10.1,10.8,10.2], borderColor: "#6b7280", backgroundColor: "transparent", tension: 0.3, borderWidth: 2.5, borderDash: [5,3] },
  ]
};

// ── FV-ECF Intervals Chart (1Y, 3Y, 5Y, 10Y) ──────────────────────────
export const fvEcfIntervals = {
  labels: ["Materials", "Financials", "Healthcare", "Technology", "Energy", "Consumer Staples", "Utilities", "Industrials"],
  datasets: [
    { label: "FV-ECF 1Y ($M)", data: [2840, 8920, 1240, 980, 3150, 1420, 850, 1180], backgroundColor: "hsl(213 75% 70% / 0.85)" },
    { label: "FV-ECF 3Y ($M)", data: [3240, 10840, 1580, 1420, 3580, 1680, 980, 1380], backgroundColor: "hsl(213 75% 50% / 0.85)" },
    { label: "FV-ECF 5Y ($M)", data: [3580, 12480, 1840, 1820, 3940, 1920, 1120, 1580], backgroundColor: "hsl(213 75% 35% / 0.85)" },
    { label: "FV-ECF 10Y ($M)", data: [4240, 15820, 2480, 2540, 4520, 2380, 1380, 1980], backgroundColor: "hsl(213 75% 22% / 0.85)" },
  ]
};

// ── FV-ECF Time Series (Rolling DCF value indicator) ──────────────────
export const fvEcfTimeSeries = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "FV-ECF 1Y", data: [1.02, 1.05, 1.08, 0.94, 0.88, 0.98, 1.01, 1.04, 1.06, 1.08, 1.04, 1.06, 1.09, 1.07], borderColor: "hsl(213 75% 70%)", backgroundColor: "hsl(213 75% 70% / 0.1)", tension: 0.3, fill: false },
    { label: "FV-ECF 3Y", data: [1.08, 1.12, 1.18, 0.98, 0.92, 1.08, 1.12, 1.16, 1.19, 1.22, 1.16, 1.20, 1.24, 1.21], borderColor: "hsl(213 75% 50%)", backgroundColor: "hsl(213 75% 50% / 0.1)", tension: 0.3, fill: false },
    { label: "FV-ECF 5Y", data: [1.15, 1.22, 1.28, 1.02, 0.96, 1.18, 1.24, 1.30, 1.34, 1.38, 1.28, 1.34, 1.38, 1.35], borderColor: "hsl(213 75% 35%)", backgroundColor: "hsl(213 75% 35% / 0.1)", tension: 0.3, fill: false },
    { label: "FV-ECF 10Y", data: [1.28, 1.38, 1.48, 1.08, 1.02, 1.38, 1.48, 1.58, 1.64, 1.72, 1.54, 1.64, 1.72, 1.68], borderColor: "hsl(213 75% 22%)", backgroundColor: "hsl(213 75% 22% / 0.1)", tension: 0.3, fill: false },
  ]
};

// ── ROA by Sector (multi-interval) ────────────────────────────────────
export const roaBySector = {
  labels: ["Materials", "Financials", "Healthcare", "Technology", "Energy", "Consumer Staples", "Utilities"],
  datasets: [
    { label: "ROA 1Y", data: [5.8, 1.2, 7.2, 9.4, 4.2, 6.1, 3.4], backgroundColor: "hsl(152 60% 65% / 0.8)" },
    { label: "ROA 3Y", data: [6.2, 1.4, 7.8, 10.2, 4.8, 6.4, 3.8], backgroundColor: "hsl(152 60% 50% / 0.8)" },
    { label: "ROA 5Y", data: [5.8, 1.5, 8.2, 11.4, 5.1, 6.8, 4.1], backgroundColor: "hsl(152 60% 40% / 0.8)" },
    { label: "ROA 10Y", data: [5.4, 1.6, 8.8, 12.1, 5.5, 7.2, 4.5], backgroundColor: "hsl(152 60% 28% / 0.8)" },
  ]
};

// ── Profit Margin by Sector ────────────────────────────────────────────
export const profitMarginBySector = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Healthcare", data: [18.2,19.4,20.1,17.8,16.4,21.2,22.4,21.8,22.4,23.1,22.8,23.4,24.1,22.8], borderColor: "#15803d", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Technology", data: [12.4,14.2,15.8,11.2,10.4,16.2,17.4,18.1,19.4,21.2,19.8,21.4,22.8,20.4], borderColor: "#7c3aed", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Financials", data: [22.4,24.1,25.8,18.4,15.2,22.8,23.4,24.8,26.1,25.4,24.8,25.1,24.4,23.8], borderColor: "#1d4ed8", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "Materials", data: [14.8,16.2,18.4,12.4,8.4,16.4,15.8,14.4,13.8,12.8,12.4,13.1,14.2,13.8], borderColor: "#b45309", backgroundColor: "transparent", tension: 0.3, borderWidth: 2 },
    { label: "ASX 200", data: [14.2,15.8,17.4,12.8,10.8,16.2,16.8,16.4,17.2,17.8,16.4,17.1,17.8,16.8], borderColor: "#6b7280", backgroundColor: "transparent", tension: 0.3, borderWidth: 2.5, borderDash: [5,3] },
  ]
};

// ── M:B Ratio — 1Y/3Y/5Y/10Y sensitivity ─────────────────────────────
export const mbRatioIntervals = {
  labels: ["<0.5","0.5-1","1-1.5","1.5-2","2-2.5","2.5-3","3-4",">4"],
  datasets: [
    { label: "1Y", data: [12, 38, 82, 94, 71, 48, 28, 14], backgroundColor: "hsl(38 60% 75% / 0.8)" },
    { label: "3Y", data: [8, 28, 74, 102, 84, 56, 34, 18], backgroundColor: "hsl(38 60% 60% / 0.8)" },
    { label: "5Y", data: [6, 22, 68, 108, 91, 62, 38, 22], backgroundColor: "hsl(38 60% 45% / 0.8)" },
    { label: "10Y", data: [4, 16, 58, 112, 98, 71, 42, 28], backgroundColor: "hsl(38 60% 30% / 0.8)" },
  ]
};

// ── TER Decomposition (Proper Waterfall) ──────────────────────────────
export const terDecompositionData = {
  labels: ["Open MC × Ke", "Dividend Yield", "Capital Gain", "Franking Credit", "TER", "TER-Ke"],
  values: [100, 4.8, 6.2, 1.4, 112.4, 2.4],
  types: ["base", "pos", "pos", "pos", "total", "pos"],
  colors: [
    "hsl(213 75% 40%)",
    "hsl(152 60% 40%)",
    "hsl(152 60% 40%)",
    "hsl(152 60% 50%)",
    "hsl(213 75% 22%)",
    "hsl(38 60% 52%)",
  ]
};

// ── TER Alpha = TER-Ke minus RA_MM (Market Risk Adjusted) ─────────────
export const terAlphaTimeSeries = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "TER-Ke (Excess Return)", data: [2.4,3.1,4.2,-1.8,-5.2,3.8,2.4,1.8,2.1,2.8,1.4,2.2,3.1,2.4], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.1)", tension: 0.3, fill: true },
    { label: "RA_MM (Market Adjustment)", data: [0.8,1.1,1.8,-0.6,-2.4,1.4,0.8,0.6,0.7,1.0,0.5,0.8,1.2,0.9], borderColor: "hsl(38 60% 52%)", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
    { label: "TER Alpha", data: [1.6,2.0,2.4,-1.2,-2.8,2.4,1.6,1.2,1.4,1.8,0.9,1.4,1.9,1.5], borderColor: "hsl(152 60% 40%)", backgroundColor: "transparent", tension: 0.3, borderWidth: 2.5 },
  ]
};

// ── EEAI Heatmap (Company × Year) ─────────────────────────────────────
export const eeaiHeatmapData = {
  companies: ["BHP","CBA","CSL","WBC","ANZ","NAB","WES","TLS","RIO","WOW","MQG","TCL","AMC","SEK","REA","COH","CAR","CPU","IEL","ALU"],
  years: ["2011","2012","2013","2014","2015","2016","2017","2018"],
  values: [
    [110, 112, 108, 105, 102, 98, 95, 92],   // BHP
    [125, 128, 132, 135, 130, 128, 131, 134], // CBA
    [142, 148, 155, 162, 158, 165, 172, 178], // CSL
    [118, 122, 126, 124, 120, 118, 122, 126], // WBC
    [114, 118, 120, 118, 114, 112, 115, 119], // ANZ
    [112, 116, 119, 117, 113, 111, 113, 117], // NAB
    [128, 132, 136, 140, 138, 142, 145, 148], // WES
    [88, 84, 80, 76, 72, 68, 65, 62],         // TLS
    [104, 108, 106, 102, 98, 95, 98, 101],    // RIO
    [118, 122, 125, 128, 125, 122, 119, 116], // WOW
    [138, 144, 148, 152, 148, 152, 156, 160], // MQG
    [122, 126, 129, 132, 130, 128, 131, 134], // TCL
    [112, 115, 118, 121, 118, 116, 119, 122], // AMC
    [145, 152, 158, 162, 156, 162, 168, 172], // SEK
    [148, 156, 164, 170, 165, 171, 178, 182], // REA
    [158, 165, 172, 178, 174, 181, 188, 192], // COH
    [142, 149, 156, 162, 158, 165, 172, 176], // CAR
    [136, 142, 148, 154, 150, 156, 162, 166], // CPU
    [148, 156, 164, 172, 168, 175, 182, 188], // IEL
    [152, 160, 168, 175, 170, 177, 184, 190], // ALU
  ]
};

// ── EP Delivered vs EP Required (EEAI Components) ─────────────────────
export const epDeliveredVsRequired = {
  labels: ["2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "EP Required (Implied by Market)", data: [8.4, 7.8, 8.2, 8.5, 8.8, 9.1, 9.4, 9.2, 9.0, 9.3, 9.5], borderColor: "hsl(38 60% 52%)", backgroundColor: "hsl(38 60% 52% / 0.1)", tension: 0.3, fill: true, borderWidth: 2.5 },
    { label: "EP Delivered (3Y Average)", data: [6.2, 4.8, 6.8, 7.2, 7.5, 7.9, 8.2, 7.8, 7.5, 7.9, 8.2], borderColor: "hsl(213 75% 40%)", backgroundColor: "transparent", tension: 0.3, borderWidth: 2.5 },
    { label: "EEAI Gap (Expectation Deficit)", type: "bar" as const, data: [2.2, 3.0, 1.4, 1.3, 1.3, 1.2, 1.2, 1.4, 1.5, 1.4, 1.3], backgroundColor: "hsl(0 70% 50% / 0.4)", yAxisID: "y2" } as any,
  ]
};

// ── Wealth Creation Absolute ($B) ──────────────────────────────────────
export const wealthCreationAbsolute = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "WC (Wealth Created, $B)", data: [48.2, 62.4, 78.1, -42.8, -18.4, 52.4, 38.2, 42.8, 56.4, 64.8, 48.2, 58.4, 72.1, 64.8], backgroundColor: (ctx: any) => ctx.raw >= 0 ? "hsl(152 60% 40% / 0.8)" : "hsl(0 70% 50% / 0.8)", borderRadius: 3 },
    { label: "WC_TERA (Risk-Adjusted, $B)", data: [38.4, 51.2, 64.8, -38.4, -14.2, 44.2, 31.8, 36.4, 48.2, 55.4, 40.8, 49.2, 61.8, 55.4], type: "line" as const, borderColor: "hsl(38 60% 52%)", backgroundColor: "transparent", tension: 0.3, borderWidth: 2, borderDash: [4,3] } as any,
  ]
};

// ── Sector Aggregation Scatter: EP% vs Market Return ──────────────────
export const sectorEpVsMarketScatter = {
  datasets: [
    { label: "Materials", data: [{x: -1.2, y: 6.4}, {x: 0.8, y: 9.2}, {x: 2.4, y: 11.8}, {x:-2.1,y:4.2}, {x:1.8,y:10.4}], backgroundColor: "#b45309", pointRadius: 8 },
    { label: "Financials", data: [{x:3.8,y:12.4},{x:4.2,y:13.8},{x:2.8,y:10.2},{x:5.4,y:15.8},{x:4.8,y:14.2}], backgroundColor: "#1d4ed8", pointRadius: 8 },
    { label: "Healthcare", data: [{x:6.2,y:16.4},{x:7.8,y:18.2},{x:8.4,y:19.4},{x:9.2,y:21.8},{x:7.4,y:17.4}], backgroundColor: "#15803d", pointRadius: 8 },
    { label: "Technology", data: [{x:7.4,y:18.4},{x:9.8,y:22.4},{x:11.2,y:24.8},{x:8.4,y:20.4},{x:10.4,y:23.2}], backgroundColor: "#7c3aed", pointRadius: 8 },
    { label: "Energy", data: [{x:-0.4,y:7.8},{x:1.4,y:10.4},{x:-1.8,y:5.4},{x:0.8,y:9.2},{x:2.1,y:11.4}], backgroundColor: "#dc2626", pointRadius: 8 },
    { label: "Consumer Staples", data: [{x:2.1,y:10.8},{x:3.4,y:12.4},{x:1.8,y:9.8},{x:4.1,y:14.2},{x:2.8,y:11.4}], backgroundColor: "#0891b2", pointRadius: 8 },
    { label: "Utilities", data: [{x:1.2,y:8.4},{x:2.4,y:10.8},{x:0.8,y:7.8},{x:3.1,y:12.4},{x:1.8,y:9.2}], backgroundColor: "#ea580c", pointRadius: 8 },
  ]
};

// ── Goodwill & FA Intensity by Sector ─────────────────────────────────
export const assetIntensityBySector = {
  labels: ["Materials", "Financials", "Healthcare", "Technology", "Energy", "Consumer Staples", "Utilities"],
  datasets: [
    { label: "FA Intensity (Fixed Assets / Revenue)", data: [0.48, 0.12, 0.28, 0.15, 0.62, 0.22, 0.85], backgroundColor: "hsl(213 75% 40% / 0.8)" },
    { label: "GW Intensity (Goodwill / Revenue)", data: [0.18, 0.08, 0.42, 0.38, 0.12, 0.28, 0.08], backgroundColor: "hsl(38 60% 52% / 0.8)" },
    { label: "OA Intensity (Operating Assets / Revenue)", data: [0.72, 0.22, 0.56, 0.42, 0.78, 0.48, 1.12], backgroundColor: "hsl(152 60% 40% / 0.8)" },
  ]
};

// ── Economic Equity Multiplier (Assets/EE) ────────────────────────────
export const econEquityMultiplier = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "ASX 200 Average", data: [2.4,2.6,2.8,2.2,2.0,2.4,2.5,2.6,2.7,2.8,2.7,2.8,2.9,2.8], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.1)", tension: 0.3, fill: true },
    { label: "Financials", data: [3.8,4.1,4.4,3.4,3.1,3.8,3.9,4.1,4.4,4.6,4.4,4.5,4.7,4.5], borderColor: "#1d4ed8", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
    { label: "Materials", data: [1.8,1.9,2.1,1.6,1.4,1.8,1.9,1.8,1.8,1.7,1.6,1.7,1.8,1.7], borderColor: "#b45309", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
  ]
};

// ── TSR vs TER vs EP% Bubble Chart (company level) ────────────────────
export const tsrTerEpBubble = {
  datasets: [
    { label: "EP Dominant", data: [
        {x:8.4,y:10.2,r:12},{x:9.2,y:11.8,r:16},{x:10.4,y:12.4,r:14},{x:7.8,y:9.4,r:10},
        {x:11.2,y:13.1,r:18},{x:8.8,y:10.8,r:12},{x:12.4,y:14.2,r:20},{x:9.4,y:11.2,r:14}
      ], backgroundColor: "hsl(152 60% 40% / 0.65)", borderColor: "hsl(152 60% 30%)", borderWidth: 1 },
    { label: "EPS Dominant", data: [
        {x:1.2,y:6.8,r:9},{x:2.4,y:7.4,r:8},{x:-0.4,y:5.2,r:7},{x:3.1,y:8.2,r:10},
        {x:0.8,y:6.4,r:8},{x:4.2,y:9.1,r:11},{x:-1.2,y:4.8,r:7},{x:2.8,y:7.8,r:9}
      ], backgroundColor: "hsl(0 70% 50% / 0.65)", borderColor: "hsl(0 70% 40%)", borderWidth: 1 },
    { label: "Middle Cohort", data: [
        {x:4.2,y:8.4,r:10},{x:5.8,y:9.8,r:12},{x:3.8,y:8.2,r:9},{x:6.4,y:10.4,r:13},
        {x:4.8,y:9.2,r:11},{x:5.2,y:9.6,r:10},{x:6.8,y:10.8,r:12},{x:4.4,y:8.8,r:10}
      ], backgroundColor: "hsl(213 75% 50% / 0.65)", borderColor: "hsl(213 75% 40%)", borderWidth: 1 },
  ]
};

// ── Effective Tax Rate Time Series ────────────────────────────────────
export const effectiveTaxRateTimeSeries = {
  labels: ["2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "ASX 200 Effective Tax Rate", data: [28.4,27.8,28.2,26.4,24.8,26.2,27.1,27.8,28.4,28.8,28.2,27.4,27.8,28.1], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.1)", tension: 0.3, fill: true },
    { label: "Australia Statutory Rate", data: [30,30,30,30,30,30,30,30,30,30,30,30,30,30], borderColor: "hsl(0 70% 50%)", backgroundColor: "transparent", tension: 0, borderDash: [6,4], borderWidth: 2 },
  ]
};

// ── Non-Div ECF vs Dividends Split ─────────────────────────────────────
export const ecfDividendSplit = {
  labels: ["2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Dividends ($B)", data: [28.4,22.8,26.2,28.8,31.4,33.8,36.4,35.2,34.8,36.4,38.2], backgroundColor: "hsl(152 60% 40% / 0.85)", stack: "ecf" },
    { label: "Capital Gains / Non-Div ECF ($B)", data: [42.1,-18.4,36.8,22.4,28.8,38.4,48.2,38.4,42.8,52.4,48.2], backgroundColor: (ctx: any) => ctx.raw >= 0 ? "hsl(213 75% 40% / 0.85)" : "hsl(0 70% 50% / 0.75)", stack: "ecf" },
  ]
};

// ── Revenue Growth vs EE Growth correlation scatter ───────────────────
export const revVsEeGrowthScatter = {
  datasets: [
    { label: "Healthcare", data: [{x:12.4,y:14.8},{x:11.8,y:13.4},{x:13.2,y:16.2},{x:10.8,y:12.4},{x:14.4,y:17.2}], backgroundColor: "#15803d", pointRadius: 7 },
    { label: "Technology", data: [{x:15.8,y:21.4},{x:14.2,y:18.8},{x:18.4,y:24.2},{x:12.4,y:16.4},{x:22.1,y:28.4}], backgroundColor: "#7c3aed", pointRadius: 7 },
    { label: "Financials", data: [{x:5.8,y:9.4},{x:6.4,y:10.2},{x:4.8,y:8.4},{x:7.2,y:11.4},{x:5.2,y:9.1}], backgroundColor: "#1d4ed8", pointRadius: 7 },
    { label: "Materials", data: [{x:4.2,y:4.8},{x:6.8,y:6.4},{x:3.4,y:3.8},{x:8.2,y:7.4},{x:2.1,y:2.8}], backgroundColor: "#b45309", pointRadius: 7 },
    { label: "Consumer Staples", data: [{x:3.8,y:4.4},{x:4.2,y:5.1},{x:3.1,y:3.8},{x:5.4,y:6.2},{x:4.8,y:5.8}], backgroundColor: "#0891b2", pointRadius: 7 },
  ]
};

// ── Pair of Bow Waves — Baseline vs New EP Expectations ───────────────
export const pairOfBowWavesData = {
  labels: Array.from({ length: 20 }, (_, i) => `Y${i - 5}`),
  datasets: [
    {
      label: "BW Baseline — Embedded EP Expectations (T₀)",
      data: [null,null,null,null,null,42,48,52,56,60,62,60,56,50,44,38,32,26,20,14].map((v,i) => i >= 5 ? v : null),
      borderColor: "hsl(38 60% 52%)", backgroundColor: "hsl(38 60% 52% / 0.12)", tension: 0.4, fill: true,
    },
    {
      label: "BW New — Revised EP Expectations (T₁)",
      data: [null,null,null,null,null,42,52,64,76,88,95,90,82,70,58,46,35,26,18,10].map((v,i) => i >= 5 ? v : null),
      borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.12)", tension: 0.4, fill: true,
    },
    {
      label: "EP Delivered (Actual)",
      data: [null,null,null,null,null,8.4,9.2,10.8,12.4,13.8,14.2,13.4,12.1,10.8,9.4,8.2,7.1,6.2,5.4,4.8].map((v,i) => i >= 5 ? v : null),
      borderColor: "hsl(152 60% 40%)", backgroundColor: "transparent", tension: 0.3, borderDash: [5,3], borderWidth: 2.5,
    },
  ]
};

// ── EP vs EPS Focus Outcome (Grouped bar — long-term comparison) ───────
export const epVsEpsFocusOutcome = {
  labels: ["Year 1", "Year 2", "Year 3", "Year 5", "Year 7", "Year 10"],
  datasets: [
    { label: "EP-Focused: EP per Share Growth", data: [3.2, 4.8, 6.4, 8.2, 10.4, 13.8], backgroundColor: "hsl(152 60% 40% / 0.85)" },
    { label: "EP-Focused: TSR", data: [11.2, 12.4, 13.8, 14.8, 15.4, 16.2], backgroundColor: "hsl(152 60% 60% / 0.85)" },
    { label: "EPS-Focused: EP per Share Growth", data: [1.2, 1.4, 1.6, 1.8, 1.6, 1.2], backgroundColor: "hsl(0 70% 50% / 0.85)" },
    { label: "EPS-Focused: TSR", data: [8.4, 8.2, 8.0, 7.8, 7.4, 7.1], backgroundColor: "hsl(0 70% 65% / 0.85)" },
  ]
};

// ── Risk Free Rate History (Rf) ────────────────────────────────────────
export const rfRateTimeSeries = {
  labels: ["2001","2002","2003","2004","2005","2006","2007","2008","2009","2010","2011","2012","2013","2014","2015","2016","2017","2018"],
  datasets: [
    { label: "Australia 10Y Bond (Rf)", data: [5.8,5.5,5.2,5.4,5.6,5.9,6.2,5.8,4.2,5.1,4.9,3.5,3.2,2.8,2.4,2.0,2.3,2.5], borderColor: "hsl(213 75% 40%)", backgroundColor: "hsl(213 75% 40% / 0.1)", tension: 0.3, fill: true },
    { label: "USA Fed Funds Rate", data: [3.5,1.75,1.0,1.5,3.0,5.25,5.25,2.0,0.25,0.25,0.25,0.25,0.25,0.25,0.5,0.75,1.5,2.5], borderColor: "hsl(0 70% 50%)", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
    { label: "UK Base Rate", data: [4.0,4.0,3.75,4.75,4.5,5.25,5.75,2.0,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.25,0.25,0.5], borderColor: "hsl(38 60% 52%)", backgroundColor: "transparent", tension: 0.3, borderDash: [4,3] },
  ]
};

// ── Comprehensive exportable metrics for new charts ────────────────────
export const additionalExportableMetrics = [
  { id: "beta_distribution", name: "Beta Distribution — ASX 300", description: "4-tier Beta distribution across ASX 300 companies (rolling 60-month OLS)", principle: "Principle 6", section: "6.1", rows: 18, format: ["CSV","JSON"] },
  { id: "beta_sector_timeseries", name: "Beta Time Series by Sector", description: "Sector-average Beta 2005–2018 (Materials, Financials, Healthcare, Technology, Energy)", principle: "Principle 6", section: "6.2", rows: 84, format: ["CSV","JSON"] },
  { id: "ke_decomposition", name: "Ke Decomposition — Rf + Beta×MRP", description: "Cost of Equity breakdown: Risk-Free Rate + Market Risk Premium component (2005–2018)", principle: "Principle 6", section: "6.3", rows: 28, format: ["CSV","JSON"] },
  { id: "cost_structure_sector", name: "Cost Structure by Sector", description: "Op/Non-Op/Tax/XO cost margin breakdown by sector", principle: "Principle 5", section: "5.1", rows: 40, format: ["CSV","JSON"] },
  { id: "revenue_growth_intervals", name: "Revenue Growth — 1Y/3Y/5Y/10Y", description: "Annualised revenue growth at 1, 3, 5, 10 year intervals by sector", principle: "Principle 5", section: "5.2", rows: 28, format: ["CSV","JSON"] },
  { id: "ee_growth_sector", name: "Economic Equity (EE) Growth by Sector", description: "Economic Equity growth rates 2005–2018 by sector", principle: "Principle 5", section: "5.3", rows: 70, format: ["CSV","JSON"] },
  { id: "fv_ecf_intervals", name: "FV-ECF by Interval — 1Y/3Y/5Y/10Y", description: "Future Value Economic Cash Flow at 1, 3, 5, 10 year intervals (DCF valuation driver)", principle: "Principle 6", section: "6.4", rows: 32, format: ["CSV","JSON","Excel"] },
  { id: "roa_intervals", name: "ROA by Sector — Multi-Interval", description: "Return on Assets at 1Y, 3Y, 5Y, 10Y annualised for each sector", principle: "Principle 5", section: "5.4", rows: 28, format: ["CSV","JSON"] },
  { id: "ter_alpha_timeseries", name: "TER Alpha — Risk-Adjusted Excess Return", description: "TER-Ke minus RA_MM (market adjustment) = company-attributable wealth creation", principle: "Principle 3", section: "3.5", rows: 42, format: ["CSV","JSON"] },
  { id: "eeai_heatmap_company", name: "EEAI Heatmap — Company × Year", description: "EEAI score (0–200) for top 20 ASX companies by fiscal year", principle: "Principle 1", section: "1.3", rows: 160, format: ["CSV","JSON","Excel"] },
  { id: "ep_delivered_vs_required", name: "EP Delivered vs EP Required", description: "3-year average EP% delivered vs market-implied EP% required (EEAI gap)", principle: "Principle 1", section: "1.4", rows: 11, format: ["CSV","JSON"] },
  { id: "wealth_creation_absolute", name: "Wealth Created ($B) — ASX 200", description: "Absolute wealth creation (WC) and risk-adjusted wealth creation (WC_TERA) in billions", principle: "Principle 2", section: "2.2", rows: 14, format: ["CSV","JSON"] },
  { id: "effective_tax_rate", name: "Effective Tax Rate — ASX 200", description: "Effective tax rate vs statutory 30% rate (2005–2018)", principle: "Principle 5", section: "5.5", rows: 28, format: ["CSV","JSON"] },
  { id: "ecf_dividend_split", name: "ECF: Dividends vs Capital Gains Split", description: "Economic Cash Flow decomposed into dividend yield and capital appreciation components", principle: "Principle 3", section: "3.3", rows: 22, format: ["CSV","JSON"] },
];
