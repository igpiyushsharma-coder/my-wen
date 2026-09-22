# Human-AI Task Efficiency & Cost Optimization System

A web app that compares human vs. AI performance on the same business
task — cost, time, and quality — and recommends whether a task should
be handled by a **Human**, **AI**, or a **Hybrid** workflow, broken
down by task difficulty, with a confidence-ranged savings projection.

> All data shipped with this project is **SAMPLE / SYNTHETIC DATA**,
> randomly generated for demo purposes. It does not represent real
> employees or real AI benchmark results.

## 1. Problem & focus

Businesses increasingly have a choice for many repetitive tasks —
assign it to a human employee, an AI system, or some mix of both. That
decision is usually made informally. This system makes it explicit,
explainable, and quality-gated, rather than a flat "AI is cheaper"
assumption.

**Primary use case:** support and back-office teams — e.g. an Indian
MSME's customer support desk — deciding how to split routine vs.
complex ticket volume between AI and staff. The task categories,
CSV-first data model, and ₹ cost figures are built around this
context; a business already exporting ticket data from a helpdesk tool
(Zendesk, Freshdesk, etc.) as CSV can plug it in with no code changes,
which is the intended integration path before any live API work.

## 2. What this version fixes (vs. the first MVP pass)

Three honest weaknesses were identified after the first build, and
this version addresses each directly:

| Weakness | Fix |
|---|---|
| Quality was one unexplained 0–10 number | Replaced with a 4-criterion rubric (accuracy, completeness, clarity, consistency); the overall score is their computed average, never entered directly |
| One flat recommendation per task, ignoring that real volume is a mix of easy and hard cases | Every task is split into **routine** (~70%) and **complex** (~30%) segments, each analyzed and recommended separately |
| Savings shown as one confident number | Savings are now a **range** (±1 standard deviation from the underlying sample records), with the point estimate shown alongside it |

The segmentation is also what makes the demo more interesting: for
every sample task, the *overall* blended view often says HUMAN (AI's
complex-case quality drags the average down), while the *routine*
segment says AI and the *complex* segment says HUMAN — a materially
more useful answer than a single verdict, and a natural moment to show
during a demo.

## 3. Features

- Sample data for 3 task categories, each split into routine/complex, with rubric-scored quality
- CSV upload for your own human/AI performance data (same rubric + difficulty format)
- Explainable weighted scoring (configurable Cost/Time/Quality weights)
- Minimum-quality-threshold gate that can veto a cheaper/faster option outright
- HUMAN / AI / HYBRID / INSUFFICIENT_DATA recommendation, with a plain-English reason citing the actual numbers and, when relevant, the weakest rubric criterion
- Segment-level analysis (routine vs. complex) alongside the overall blended view
- Monthly & yearly savings projected as a range, not a single fabricated-looking number
- Dashboard with charts; Settings page to tune weights/threshold live and watch recommendations change
- Runs fully offline — no external AI API required (Demo Mode by construction)

## 4. Architecture

```
Browser (charts + forms)
      |
      v
Flask app (app.py) -- page routes + JSON API
      |
      v
services/
  comparison_engine.py     -- averages (overall or per segment) + normalization + weighted score
                               + quality rubric breakdown + raw values for confidence ranges
  recommendation_engine.py -- quality-gated decision + explanation, overall AND per segment
  cost_calculator.py       -- monthly/yearly savings as a confidence range
  data_processor.py        -- CSV validation (rubric + difficulty) + insertion
  ai_service.py             -- optional live API stub (not active by default)
      |
      v
SQLite database (database/app.db)
```

## 5. Technology stack

Python, Flask, SQLite, pandas, HTML/CSS/vanilla JS, Chart.js (CDN).

## 6. Database schema

**tasks** — `id, name, description, category`

**human_performance** — `id, task_id, worker_id, difficulty, time_seconds, labor_cost, quality_accuracy, quality_completeness, quality_clarity, quality_consistency, quality_score, notes`

**ai_performance** — `id, task_id, model_name, difficulty, time_seconds, input_tokens, output_tokens, api_cost, quality_accuracy, quality_completeness, quality_clarity, quality_consistency, quality_score`

**task_results** — `id, task_id, segment, human_score, ai_score, recommendation, estimated_savings, created_at` (one row per Analysis run, per segment)

`quality_score` is always the computed average of the 4 rubric columns — it is never accepted as raw input, in CSV uploads or otherwise.

## 7. Comparison & scoring methodology

Cost/time/quality are normalized to 0–100 via min-max normalization
*between the human and AI averages being compared* (cheaper/faster/
higher-quality → closer to 100). This is deliberately simple for an
explainable MVP — see Limitations for the known trade-off.

```
Efficiency Score = (Weight_cost × Cost Score) + (Weight_time × Time Score) + (Weight_quality × Quality Score)
```
Default weights: Cost 40%, Time 30%, Quality 30% (configurable).

Quality itself is the average of 4 rubric sub-criteria (accuracy,
completeness, clarity, consistency), each scored 1–10 — not a single
unexplained number.

## 8. Recommendation logic (per segment, and overall)

1. Neither side meets the minimum quality threshold (default 7/10) → `INSUFFICIENT_DATA`
2. Only one side meets it → that side wins automatically, regardless of score
3. Both meet it: scores within 10 points → `HYBRID`; AI wins on score but human quality is notably higher → `HYBRID` (AI drafts, human reviews); otherwise the higher-scoring side wins

This logic runs three times per Analysis click: once for the whole
task blended together, and once each for the routine and complex
segments — so a single task can legitimately get different
recommendations for different slices of its volume.

## 9. Savings as a range, not a point estimate

Monthly/yearly savings are computed from the *individual* recorded
cost values (not just their average), and reported as mean ± 1
standard deviation. A wide range is itself informative — it signals
the estimate needs more data before being treated as reliable. Segment
savings additionally split the entered monthly volume by the observed
routine/complex proportion in the sample — a stated modeling
assumption, not a measured fact, and surfaced as such in the UI.

## 10. Installation & running

```bash
cd human-ai-optimizer
pip install -r requirements.txt
python3 generate_sample_data.py
python3 setup_database.py
python3 app.py
```
Open **http://127.0.0.1:5000**.

## 11. Demo mode

True by construction — no code path makes an external network call.
Works identically with or without internet access.

## 12. Optional live AI API integration

`services/ai_service.py` is a documented, inactive stub for wiring in
a real API later (see `.env.example`). Deliberately not called by the
app, to keep the hackathon demo dependency-free.

## 13. Honest limitations

- Quality rubric scores are still self-reported/estimated, not
  independently verified against ground truth — the rubric makes the
  number explainable, not necessarily objectively accurate. A
  production version would need inter-rater checks or automated eval.
- Pairwise min-max normalization shows which side is better, not
  precisely by how much, when one side sweeps all three metrics.
- The routine/complex volume split (70/30) and the confidence range
  (±1 std, assuming independence between human and AI cost variance)
  are stated modeling assumptions, not measured facts — both are
  surfaced in the UI rather than hidden inside a single confident number.
- No authentication / multi-user support — single local instance only.

## 14. Future scope

**Phase 2:** direct CSV import from helpdesk tools (Zendesk/Freshdesk exports), more AI providers, more task categories, historical analytics.
**Phase 3:** freelancer mode — businesses post tasks, freelancers offer human execution alongside AI options.
**Phase 4:** full human + AI task marketplace, enterprise workflow optimization platform.
