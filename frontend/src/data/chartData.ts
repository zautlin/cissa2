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
