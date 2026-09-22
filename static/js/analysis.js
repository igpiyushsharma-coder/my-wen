// analysis.js
// Calls /api/analyze and renders: the overall (blended) result, then
// the routine and complex segments side by side -- so the page shows
// both "the simple answer" and "the more useful, segmented answer."

const REC_STYLE = {
  "AI RECOMMENDED": { cls: "ai", badgeCls: "badge-ai" },
  "HUMAN RECOMMENDED": { cls: "human", badgeCls: "badge-human" },
  "HYBRID RECOMMENDED": { cls: "hybrid", badgeCls: "badge-hybrid" },
  "INSUFFICIENT_DATA": { cls: "insufficient", badgeCls: "badge-insufficient" },
};

function preselectTaskFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const taskId = params.get("task_id");
  if (taskId) document.getElementById("task-select").value = taskId;
}

function fmtRs(n) {
  return `₹${Math.round(n).toLocaleString("en-IN")}`;
}

function qualityBreakdownHtml(breakdown) {
  if (!breakdown) return "";
  const rows = ["accuracy", "completeness", "clarity", "consistency"].map(
    (c) => `<tr><td style="text-transform:capitalize;">${c}</td><td class="num">${breakdown.human[c]}/10</td><td class="num">${breakdown.ai[c]}/10</td></tr>`
  ).join("");
  return `
    <details style="margin-top:14px;">
      <summary style="cursor:pointer;font-size:13px;color:var(--ink-soft);">Quality rubric breakdown</summary>
      <table style="margin-top:8px;">
        <thead><tr><th>Criterion</th><th class="num">Human</th><th class="num">AI</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

function savingsHtml(savings) {
  if (!savings) return "";
  return `
    <div class="grid-2" style="margin-top:18px;">
      <div>
        <div class="label" style="font-size:12.5px;color:var(--ink-soft);">Est. monthly savings (range)</div>
        <div class="savings-figure" style="font-size:26px;">${fmtRs(savings.monthly_savings_low)} – ${fmtRs(savings.monthly_savings_high)}</div>
      </div>
      <div>
        <div class="label" style="font-size:12.5px;color:var(--ink-soft);">Est. yearly savings (range)</div>
        <div class="savings-figure" style="font-size:26px;">${fmtRs(savings.yearly_savings_low)} – ${fmtRs(savings.yearly_savings_high)}</div>
      </div>
    </div>
    <p class="note">Point estimate: ${fmtRs(savings.monthly_savings)}/month. Range reflects variation across
    ${savings.sample_size.human_records} human and ${savings.sample_size.ai_records} AI sample records (±1 standard deviation) —
    not a guarantee. Based on ${savings.monthly_volume.toLocaleString("en-IN")} tasks/month.
    Time saved: ${savings.time_saved_hours.toLocaleString("en-IN")} hours/month.</p>
  `;
}

function resultCardHtml(title, result, isOverall) {
  const style = REC_STYLE[result.recommendation] || REC_STYLE["INSUFFICIENT_DATA"];

  if (!result.raw_averages) {
    return `
      <div class="card result-panel insufficient" style="margin-bottom:16px;">
        <h3>${title}</h3>
        <p class="explanation">${result.explanation}</p>
      </div>`;
  }

  const h = result.raw_averages.human;
  const a = result.raw_averages.ai;
  const proportionNote = (!isOverall && result.proportion !== undefined)
    ? `<span class="note" style="margin-left:8px;">(~${Math.round(result.proportion * 100)}% of sample volume)</span>` : "";

  return `
    <div class="card result-panel ${style.cls}" style="margin-bottom:16px;">
      <div style="display:flex; align-items:center; justify-content:space-between;">
        <h3 style="margin:0;">${title}</h3>
        <span class="badge ${style.badgeCls}">${result.recommendation}</span>
      </div>
      ${proportionNote}
      <p class="explanation">${result.explanation}</p>

      <table style="margin-top:14px;">
        <thead><tr><th></th><th class="num">Avg. time</th><th class="num">Avg. cost</th><th class="num">Avg. quality</th><th class="num">Score</th></tr></thead>
        <tbody>
          <tr><td>Human</td><td class="num">${h.time.toFixed(1)}s</td><td class="num">₹${h.cost.toFixed(2)}</td><td class="num">${h.quality.toFixed(1)}/10</td><td class="num">${result.final_scores.human.toFixed(1)}</td></tr>
          <tr><td>AI</td><td class="num">${a.time.toFixed(1)}s</td><td class="num">₹${a.cost.toFixed(4)}</td><td class="num">${a.quality.toFixed(1)}/10</td><td class="num">${result.final_scores.ai.toFixed(1)}</td></tr>
        </tbody>
      </table>

      ${qualityBreakdownHtml(result.quality_breakdown)}
      ${savingsHtml(result.savings)}
    </div>`;
}

function renderResult(data) {
  const container = document.getElementById("result-container");

  let html = `<div class="section"><div class="section-title"><h2>Overall (all difficulty levels blended)</h2></div>`;
  html += resultCardHtml(data.task_name + " — overall", data.overall, true);
  html += `</div>`;

  const segmentKeys = Object.keys(data.segments || {});
  if (segmentKeys.length > 0) {
    html += `<div class="section"><div class="section-title"><h2>By difficulty segment</h2></div>`;
    html += `<p class="note" style="margin-bottom:14px;">Real task volume is rarely uniform — most instances are routine, a smaller share are complex/edge cases. Splitting the comparison this way often changes the recommendation.</p>`;
    html += `<div class="grid-2">`;
    for (const key of segmentKeys) {
      const label = key.charAt(0).toUpperCase() + key.slice(1);
      html += resultCardHtml(label + " cases", data.segments[key], false);
    }
    html += `</div></div>`;
  }

  container.innerHTML = html;
}

async function runAnalysis() {
  const taskId = document.getElementById("task-select").value;
  const monthlyVolume = document.getElementById("volume-input").value;
  const minQuality = document.getElementById("quality-input").value;
  const container = document.getElementById("result-container");

  if (!taskId) {
    container.innerHTML = '<div class="status-msg err">No task selected — add data on the Data page first.</div>';
    return;
  }

  container.innerHTML = '<p class="note">Running analysis…</p>';

  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, monthly_volume: monthlyVolume, min_quality: minQuality }),
  });

  const data = await res.json();

  if (!res.ok) {
    container.innerHTML = `<div class="status-msg err">${data.error || "Something went wrong."}</div>`;
    return;
  }

  renderResult(data);
}

preselectTaskFromUrl();
document.getElementById("analyze-btn").addEventListener("click", runAnalysis);
