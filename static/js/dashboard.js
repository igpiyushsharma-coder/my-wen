// dashboard.js
// Fetches /api/dashboard-data and fills in the metric strip + 4 charts.

const AI_COLOR = "#6F7352";
const HUMAN_COLOR = "#2B2925";
const HYBRID_COLOR = "#A6533B";
const INSUFFICIENT_COLOR = "#8C8175";
const GRID_COLOR = "rgba(59, 48, 40, 0.12)";

const sharedChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { usePointStyle: true, boxWidth: 8, padding: 18 },
    },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true, grid: { color: GRID_COLOR } },
  },
};

function comparisonChartOptions(useAiAxis = false) {
  if (!useAiAxis) return sharedChartOptions;

  return {
    ...sharedChartOptions,
    scales: {
      ...sharedChartOptions.scales,
      y: {
        ...sharedChartOptions.scales.y,
        position: "left",
        title: { display: true, text: "Human", color: HUMAN_COLOR },
      },
      "ai-axis": {
        beginAtZero: true,
        position: "right",
        grid: { drawOnChartArea: false },
        ticks: { color: AI_COLOR },
        title: { display: true, text: "AI", color: AI_COLOR },
      },
    },
  };
}

function comparisonDatasets(humanLabel, aiLabel, humanData, aiData, useAiAxis = false) {
  return [
    {
      label: humanLabel,
      data: humanData,
      backgroundColor: HUMAN_COLOR,
      borderColor: HUMAN_COLOR,
      borderWidth: 1,
      borderRadius: 6,
      borderSkipped: false,
      maxBarThickness: 34,
    },
    {
      label: aiLabel,
      data: aiData,
      backgroundColor: AI_COLOR,
      borderColor: "#555A3D",
      borderWidth: 2,
      borderRadius: 6,
      borderSkipped: false,
      // AI values are much smaller than human values in cost/time charts.
      // Keep the real data but guarantee a visible bar at the baseline.
      minBarLength: 10,
      maxBarThickness: 34,
      yAxisID: useAiAxis ? "ai-axis" : "y",
      order: 0,
    },
  ];
}

async function loadDashboard() {
  const res = await fetch("/api/dashboard-data");
  const data = await res.json();

  // --- Metric strip ---
  const metrics = document.querySelectorAll("#metric-strip .metric .value");
  const counts = data.recommendation_counts;
  const values = [
    data.total_tasks,
    counts["AI RECOMMENDED"] || 0,
    counts["HUMAN RECOMMENDED"] || 0,
    counts["HYBRID RECOMMENDED"] || 0,
    `₹${data.estimated_monthly_savings.toLocaleString("en-IN")}`,
    `₹${data.estimated_yearly_savings.toLocaleString("en-IN")}`,
  ];
  metrics.forEach((el, i) => {
    el.textContent = values[i];
    el.classList.remove("is-loaded");
    void el.offsetWidth;
    el.classList.add("is-loaded");
  });

  document.getElementById("volume-note").textContent =
    `Savings figures assume ${data.assumed_monthly_volume_per_task.toLocaleString("en-IN")} tasks/month per task (set in Settings). Run Analysis for a task-specific volume.`;

  const charts = data.charts;

  if (charts.task_labels.length === 0) {
    return; // no data yet, leave charts empty
  }

  // --- Cost chart ---
  new Chart(document.getElementById("costChart"), {
    type: "bar",
    data: {
      labels: charts.task_labels,
      datasets: comparisonDatasets(
        "Human (₹)", "AI (₹)", charts.human_costs, charts.ai_costs, true
      ),
    },
    options: comparisonChartOptions(true)
  });

  // --- Time chart ---
  new Chart(document.getElementById("timeChart"), {
    type: "bar",
    data: {
      labels: charts.task_labels,
      datasets: comparisonDatasets(
        "Human (sec)", "AI (sec)", charts.human_times, charts.ai_times, true
      ),
    },
    options: comparisonChartOptions(true),
  });

  // --- Quality chart ---
  new Chart(document.getElementById("qualityChart"), {
    type: "bar",
    data: {
      labels: charts.task_labels,
      datasets: comparisonDatasets(
        "Human (/10)", "AI (/10)", charts.human_qualities, charts.ai_qualities
      ),
    },
    options: {
      ...sharedChartOptions,
      scales: { ...sharedChartOptions.scales, y: { ...sharedChartOptions.scales.y, max: 10 } },
    },
  });

  // --- Recommendation distribution ---
  new Chart(document.getElementById("recChart"), {
    type: "doughnut",
    data: {
      labels: Object.keys(counts),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: [AI_COLOR, HUMAN_COLOR, HYBRID_COLOR, INSUFFICIENT_COLOR],
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 16 } } },
    },
  });
}

loadDashboard();
