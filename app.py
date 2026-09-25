"""
app.py

WHAT THIS FILE DOES:
This is the Flask web server -- it ties every service module together
into an actual website you can click around in.

PAGES (rendered HTML):
  /                -> public landing page
  /dashboard       -> overview: totals, recommendation breakdown, charts
  /tasks           -> list of all tasks in the database
  /analysis        -> pick a task + monthly volume -> see full analysis
  /data            -> view data summary + upload new CSVs
  /settings        -> configure weights, quality threshold, AI pricing

JSON API (used by the frontend's JavaScript):
  GET  /api/dashboard-data   -> aggregate stats + chart data
  POST /api/analyze          -> run comparison+recommendation for one task
  POST /api/upload/human     -> upload a human performance CSV
  POST /api/upload/ai        -> upload an AI performance CSV
  GET  /api/settings         -> current settings
  POST /api/settings         -> update settings

DEMO MODE:
This whole app only ever reads/writes the local SQLite database and
local CSV files -- there is no live external AI API call anywhere in
the code, so it always works offline. This satisfies the spec's
"must work without an external AI API" requirement by construction
rather than needing a special toggle.
"""

from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import os
import json
import csv
from io import StringIO

from services.comparison_engine import (
    compute_scores_for_all_tasks, compute_scores_for_task,
    get_raw_cost_time, get_available_difficulties, get_difficulty_proportions,
)
from services.recommendation_engine import build_recommendation, build_segmented_recommendations
from services.cost_calculator import calculate_savings, calculate_savings_with_confidence
from services.data_processor import process_human_csv, process_ai_csv, CSVValidationError
import config

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "app.db")


def ensure_db_schema():
    """Creates/repairs the SQLite schema if the database is missing tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        with open(os.path.join(BASE_DIR, "database", "schema.sql"), "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def get_db():
    """Opens a new database connection for this request."""
    ensure_db_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------
# PAGE ROUTES (render HTML templates)
# ---------------------------------------------------------------

@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/tasks")
def tasks():
    conn = get_db()
    task_rows = conn.execute("SELECT id, name, description, category FROM tasks ORDER BY name").fetchall()
    conn.close()
    return render_template("tasks.html", tasks=task_rows)


@app.route("/analysis")
def analysis():
    conn = get_db()
    task_rows = conn.execute("SELECT id, name, description FROM tasks ORDER BY name").fetchall()
    conn.close()
    settings = config.load_settings()
    return render_template(
        "analysis.html",
        tasks=task_rows,
        default_volume=settings["default_monthly_volume"],
        default_min_quality=settings["min_quality_threshold"],
    )


@app.route("/data")
def data_page():
    conn = get_db()
    task_rows = conn.execute(
        """SELECT t.id, t.name, t.category,
                  (SELECT COUNT(*) FROM human_performance WHERE task_id = t.id) AS human_count,
                  (SELECT COUNT(*) FROM ai_performance WHERE task_id = t.id) AS ai_count
           FROM tasks t ORDER BY t.name"""
    ).fetchall()
    conn.close()
    return render_template("data.html", tasks=task_rows)


@app.route("/settings")
def settings_page():
    return render_template("settings.html", settings=config.load_settings())


# ---------------------------------------------------------------
# JSON API ROUTES
# ---------------------------------------------------------------

@app.route("/api/dashboard-data")
def api_dashboard_data():
    """
    Computes recommendations for every task and returns aggregate
    stats + chart-ready data for the dashboard page.
    """
    settings = config.load_settings()
    conn = get_db()
    task_rows = conn.execute("SELECT id, name FROM tasks ORDER BY name").fetchall()

    results = []
    for row in task_rows:
        rec = build_recommendation(
            row["id"], row["name"], conn,
            weights=settings["weights"],
            min_quality=settings["min_quality_threshold"],
        )
        results.append(rec)

    conn.close()

    # --- Aggregate counts ---
    counts = {"AI RECOMMENDED": 0, "HUMAN RECOMMENDED": 0, "HYBRID RECOMMENDED": 0, "INSUFFICIENT_DATA": 0}
    total_human_cost, total_ai_cost = 0.0, 0.0
    valid_tasks = 0
    monthly_savings_total = 0.0

    task_labels, human_costs, ai_costs, human_times, ai_times, human_qualities, ai_qualities = [], [], [], [], [], [], []

    for r in results:
        counts[r["recommendation"]] = counts.get(r["recommendation"], 0) + 1
        if r["raw_averages"] is not None:
            valid_tasks += 1
            h, a = r["raw_averages"]["human"], r["raw_averages"]["ai"]
            total_human_cost += h["cost"]
            total_ai_cost += a["cost"]

            savings = calculate_savings(
                h["cost"], a["cost"], h["time"], a["time"],
                settings["default_monthly_volume"],
            )
            monthly_savings_total += savings["monthly_savings"]

            task_labels.append(r["task_name"])
            human_costs.append(round(h["cost"], 2))
            ai_costs.append(round(a["cost"], 4))
            human_times.append(round(h["time"], 1))
            ai_times.append(round(a["time"], 1))
            human_qualities.append(round(h["quality"], 1))
            ai_qualities.append(round(a["quality"], 1))

    avg_human_cost = round(total_human_cost / valid_tasks, 2) if valid_tasks else 0
    avg_ai_cost = round(total_ai_cost / valid_tasks, 4) if valid_tasks else 0

    return jsonify({
        "total_tasks": len(task_rows),
        "recommendation_counts": counts,
        "avg_human_cost": avg_human_cost,
        "avg_ai_cost": avg_ai_cost,
        "estimated_monthly_savings": round(monthly_savings_total, 2),
        "estimated_yearly_savings": round(monthly_savings_total * 12, 2),
        "assumed_monthly_volume_per_task": settings["default_monthly_volume"],
        "charts": {
            "task_labels": task_labels,
            "human_costs": human_costs,
            "ai_costs": ai_costs,
            "human_times": human_times,
            "ai_times": ai_times,
            "human_qualities": human_qualities,
            "ai_qualities": ai_qualities,
        },
    })


def _savings_for(conn, task_id, difficulty, monthly_volume):
    """Builds confidence-range savings for one task/segment, or None if there's no volume/data."""
    if monthly_volume <= 0:
        return None
    raw = get_raw_cost_time(conn, task_id, difficulty=difficulty)
    if not raw["human_costs"] or not raw["ai_costs"]:
        return None
    return calculate_savings_with_confidence(
        raw["human_costs"], raw["ai_costs"], raw["human_times"], raw["ai_times"], monthly_volume,
    )


def _record_analysis_history(conn, task_id, task_name, overall_rec, monthly_volume, min_quality):
    """Stores a lightweight summary of the analysis run to support recent-history UI."""
    if overall_rec.get("raw_averages") is None:
        return

    summary = {
        "task_name": task_name,
        "recommendation": overall_rec.get("recommendation"),
        "monthly_volume": monthly_volume,
        "min_quality": min_quality,
        "final_scores": overall_rec.get("final_scores"),
        "raw_averages": overall_rec.get("raw_averages"),
    }

    conn.execute(
        """
        INSERT INTO analysis_history (task_id, task_name, recommendation, monthly_volume, min_quality, summary_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            task_name,
            overall_rec.get("recommendation"),
            monthly_volume,
            min_quality,
            json.dumps(summary, default=str),
        ),
    )
    conn.commit()


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Runs the full pipeline for ONE task and returns BOTH:
      - "overall": the whole task blended together (all difficulty
        levels combined) -- the simple, single-number view.
      - "segments": routine vs. complex broken out separately, each
        with its own recommendation and savings -- this is what lets
        the system say "AI for routine, Human/Hybrid for complex"
        instead of one flat answer.

    Segment savings split the user's monthly_volume across segments
    using the observed routine/complex proportion in the sample data
    (see get_difficulty_proportions) -- a modeling assumption, surfaced
    in the response as "proportion" so the UI can be transparent about it.

    Every savings figure is a confidence RANGE (based on the spread of
    the underlying records), not a single point estimate presented as fact.
    """
    body = request.get_json(force=True)
    task_id = body.get("task_id")
    monthly_volume = int(body.get("monthly_volume", 0) or 0)

    settings = config.load_settings()
    weights = body.get("weights") or settings["weights"]
    min_quality = float(body.get("min_quality", settings["min_quality_threshold"]))

    conn = get_db()
    task_row = conn.execute("SELECT id, name FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task_row:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    tid, tname = task_row["id"], task_row["name"]

    # --- Overall (blended) view ---
    overall_rec = build_recommendation(tid, tname, conn, weights=weights, min_quality=min_quality)
    overall_savings = _savings_for(conn, tid, None, monthly_volume)
    _record_analysis_history(conn, tid, tname, overall_rec, monthly_volume, min_quality)

    if overall_rec["raw_averages"] is not None and monthly_volume > 0:
        conn.execute(
            """INSERT INTO task_results (task_id, segment, human_score, ai_score, recommendation, estimated_savings)
               VALUES (?, 'overall', ?, ?, ?, ?)""",
            (tid, overall_rec["final_scores"]["human"], overall_rec["final_scores"]["ai"],
             overall_rec["recommendation"], overall_savings["monthly_savings"] if overall_savings else None),
        )
        conn.commit()

    # --- Segmented view ---
    proportions = get_difficulty_proportions(conn, tid)
    segment_recs = build_segmented_recommendations(tid, tname, conn, weights=weights, min_quality=min_quality)

    segments_out = {}
    for difficulty, rec in segment_recs.items():
        segment_volume = round(monthly_volume * proportions.get(difficulty, 0)) if monthly_volume > 0 else 0
        segment_savings = _savings_for(conn, tid, difficulty, segment_volume)

        if rec["raw_averages"] is not None and segment_savings:
            conn.execute(
                """INSERT INTO task_results (task_id, segment, human_score, ai_score, recommendation, estimated_savings)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tid, difficulty, rec["final_scores"]["human"], rec["final_scores"]["ai"],
                 rec["recommendation"], segment_savings["monthly_savings"]),
            )
            conn.commit()

        segments_out[difficulty] = {
            "proportion": round(proportions.get(difficulty, 0), 2),
            "recommendation": rec["recommendation"],
            "explanation": rec["explanation"],
            "raw_averages": rec["raw_averages"],
            "final_scores": rec["final_scores"],
            "quality_breakdown": rec["quality_breakdown"],
            "savings": segment_savings,
        }

    conn.close()

    return jsonify({
        "task_name": tname,
        "overall": {
            "recommendation": overall_rec["recommendation"],
            "explanation": overall_rec["explanation"],
            "raw_averages": overall_rec["raw_averages"],
            "final_scores": overall_rec["final_scores"],
            "quality_breakdown": overall_rec["quality_breakdown"],
            "savings": overall_savings,
        },
        "segments": segments_out,
    })


@app.route("/api/upload/human", methods=["POST"])
def api_upload_human():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    conn = get_db()
    try:
        count = process_human_csv(conn, request.files["file"])
        return jsonify({"message": f"Uploaded {count} human performance rows."})
    except CSVValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not process file: {e}"}), 400
    finally:
        conn.close()


@app.route("/api/upload/ai", methods=["POST"])
def api_upload_ai():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    conn = get_db()
    try:
        count = process_ai_csv(conn, request.files["file"])
        return jsonify({"message": f"Uploaded {count} AI performance rows."})
    except CSVValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not process file: {e}"}), 400
    finally:
        conn.close()


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(config.load_settings())

    body = request.get_json(force=True)
    settings = config.load_settings()

    if "weights" in body:
        settings["weights"] = body["weights"]
    if "min_quality_threshold" in body:
        settings["min_quality_threshold"] = float(body["min_quality_threshold"])
    if "default_monthly_volume" in body:
            settings["default_monthly_volume"] = int(body["default_monthly_volume"])

    config.save_settings(settings)
    return jsonify({"message": "Settings updated.", "settings": settings})


@app.route("/api/history")
def api_history():
    """Returns recent analysis history for the dashboard or demo reporting."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, task_id, task_name, recommendation, monthly_volume, min_quality, created_at, summary_json
        FROM analysis_history
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()
    conn.close()

    history = []
    for row in rows:
        entry = {
            "id": row["id"],
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "recommendation": row["recommendation"],
            "monthly_volume": row["monthly_volume"],
            "min_quality": row["min_quality"],
            "created_at": row["created_at"],
        }
        if row["summary_json"]:
            try:
                entry["summary"] = json.loads(row["summary_json"])
            except Exception:
                entry["summary"] = {}
        history.append(entry)

    return jsonify({"history": history})


@app.route("/api/report/<int:task_id>")
def api_report(task_id):
    """Exports one task's latest analysis summary as a simple JSON report."""
    conn = get_db()
    row = conn.execute(
        """
        SELECT task_name, recommendation, monthly_volume, min_quality, created_at, summary_json
        FROM analysis_history
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No analysis report found for this task."}), 404

    body = {"task_name": row["task_name"], "recommendation": row["recommendation"], "monthly_volume": row["monthly_volume"], "min_quality": row["min_quality"], "created_at": row["created_at"]}
    if row["summary_json"]:
        try:
            body["summary"] = json.loads(row["summary_json"])
        except Exception:
            body["summary"] = {}
    return jsonify(body)


@app.route("/api/export/<int:task_id>")
def api_export_report(task_id):
    """Returns CSV export of the latest saved analysis for a task."""
    conn = get_db()
    row = conn.execute(
        """
        SELECT task_name, recommendation, monthly_volume, min_quality, created_at, summary_json
        FROM analysis_history
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No analysis report found for this task."}), 404

    summary = {}
    if row["summary_json"]:
        try:
            summary = json.loads(row["summary_json"])
        except Exception:
            summary = {}

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["task_name", "recommendation", "monthly_volume", "min_quality", "created_at"])
    writer.writerow([row["task_name"], row["recommendation"], row["monthly_volume"], row["min_quality"], row["created_at"]])
    writer.writerow([])
    writer.writerow(["field", "value"])
    for key, value in summary.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                writer.writerow([f"{key}.{sub_key}", sub_value])
        else:
            writer.writerow([key, value])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={row['task_name']}_analysis_report.csv"},
    )


if __name__ == "__main__":
    ensure_db_schema()
    if not os.path.exists(DB_PATH):
        print("No database found. Run setup_database.py first!.")
    app.run(debug=True,port=5000,host='0.0.0.0')