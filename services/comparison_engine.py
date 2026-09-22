"""
comparison_engine.py

WHAT THIS FILE DOES:
For each task (optionally filtered to a 'routine' or 'complex'
difficulty segment), this module:
  1. Computes the average time / cost / quality for Human and for AI
  2. Normalizes those onto a 0-100 scale so they're comparable
  3. Combines them into a single weighted "efficiency score" per side

It also exposes:
  - get_quality_breakdown(): the 4 rubric sub-scores behind the
    average quality_score, so a recommendation can be explained by
    what it's actually made of, not just asserted.
  - get_raw_cost_time(): the individual cost/time values behind an
    average, used by cost_calculator.py to build a confidence range
    instead of a single point-estimate savings number.
  - get_available_difficulties() / get_difficulty_proportions(): what
    segments exist for a task, and roughly what share of volume each
    represents in the sample data.

This file does NOT decide the final HUMAN/AI/HYBRID recommendation --
that's recommendation_engine.py. Keeping the math and the decision
rules separate means either can change without touching the other.

NORMALIZATION (unchanged from the original design, explained again):
Time is in seconds, cost is in rupees, quality is 0-10 -- not directly
comparable. Min-max normalization puts all three on 0-100:
  - Cost & time: lower is better -> cheaper/faster side scores higher
  - Quality: higher is better -> higher-quality side scores higher
  - If both sides are equal on a metric, both score 50
"""

import sqlite3

DB_PATH = "database/app.db"

DEFAULT_WEIGHTS = {
    "cost": 0.40,
    "time": 0.30,
    "quality": 0.30,
}

QUALITY_CRITERIA = ["quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency"]


def _difficulty_clause(difficulty):
    """Returns (sql_fragment, params) for an optional difficulty filter."""
    if difficulty:
        return "AND difficulty = ?", (difficulty,)
    return "", ()


def get_task_averages(conn, task_id, difficulty=None):
    """
    Returns average time/cost/quality for human and AI on this task,
    optionally restricted to one difficulty segment ('routine' or
    'complex'). Returns None if either side has no matching data.
    """
    clause, extra = _difficulty_clause(difficulty)

    h_time, h_cost, h_quality = conn.execute(
        f"""SELECT AVG(time_seconds), AVG(labor_cost), AVG(quality_score)
            FROM human_performance WHERE task_id = ? {clause}""",
        (task_id, *extra),
    ).fetchone()

    a_time, a_cost, a_quality = conn.execute(
        f"""SELECT AVG(time_seconds), AVG(api_cost), AVG(quality_score)
            FROM ai_performance WHERE task_id = ? {clause}""",
        (task_id, *extra),
    ).fetchone()

    if None in (h_time, h_cost, h_quality, a_time, a_cost, a_quality):
        return None

    return {
        "human": {"time": h_time, "cost": h_cost, "quality": h_quality},
        "ai": {"time": a_time, "cost": a_cost, "quality": a_quality},
    }


def get_quality_breakdown(conn, task_id, difficulty=None):
    """
    Returns the average of each of the 4 rubric sub-criteria, for
    human and AI, so a quality number can be explained by what it's
    made of instead of asserted as a single opaque figure.
    """
    clause, extra = _difficulty_clause(difficulty)
    cols = ", ".join(f"AVG({c})" for c in QUALITY_CRITERIA)

    h_row = conn.execute(
        f"SELECT {cols} FROM human_performance WHERE task_id = ? {clause}", (task_id, *extra)
    ).fetchone()
    a_row = conn.execute(
        f"SELECT {cols} FROM ai_performance WHERE task_id = ? {clause}", (task_id, *extra)
    ).fetchone()

    if h_row is None or a_row is None or None in h_row or None in a_row:
        return None

    labels = ["accuracy", "completeness", "clarity", "consistency"]
    return {
        "human": {label: round(val, 1) for label, val in zip(labels, h_row)},
        "ai": {label: round(val, 1) for label, val in zip(labels, a_row)},
    }


def get_raw_cost_time(conn, task_id, difficulty=None):
    """
    Returns the individual (not averaged) cost and time values behind
    a task's averages, so a confidence range can be computed from
    their spread rather than presenting one point estimate as if it
    were certain.
    """
    clause, extra = _difficulty_clause(difficulty)

    human_rows = conn.execute(
        f"SELECT labor_cost, time_seconds FROM human_performance WHERE task_id = ? {clause}",
        (task_id, *extra),
    ).fetchall()
    ai_rows = conn.execute(
        f"SELECT api_cost, time_seconds FROM ai_performance WHERE task_id = ? {clause}",
        (task_id, *extra),
    ).fetchall()

    return {
        "human_costs": [r[0] for r in human_rows],
        "human_times": [r[1] for r in human_rows],
        "ai_costs": [r[0] for r in ai_rows],
        "ai_times": [r[1] for r in ai_rows],
    }


def get_available_difficulties(conn, task_id):
    """Returns the distinct difficulty segments that have data for this task."""
    rows = conn.execute(
        """SELECT DISTINCT difficulty FROM human_performance WHERE task_id = ?
           UNION
           SELECT DISTINCT difficulty FROM ai_performance WHERE task_id = ?""",
        (task_id, task_id),
    ).fetchall()
    return sorted((r[0] for r in rows), reverse=True)  # 'routine' before 'complex'


def get_difficulty_proportions(conn, task_id):
    """
    Estimates what share of real task volume each difficulty segment
    represents, using the human worker record counts in the sample
    data as a proxy. Used to split a monthly volume across segments
    for a more realistic blended savings estimate. This is a modeling
    assumption, not a measured fact -- documented as such wherever it's used.
    """
    rows = conn.execute(
        "SELECT difficulty, COUNT(*) FROM human_performance WHERE task_id = ? GROUP BY difficulty",
        (task_id,),
    ).fetchall()
    total = sum(count for _, count in rows)
    if total == 0:
        return {}
    return {difficulty: count / total for difficulty, count in rows}


def normalize_pair(human_value, ai_value, higher_is_better):
    """Converts a (human_value, ai_value) pair into 0-100 scores via min-max normalization."""
    best = max(human_value, ai_value) if higher_is_better else min(human_value, ai_value)
    worst = min(human_value, ai_value) if higher_is_better else max(human_value, ai_value)

    if best == worst:
        return 50.0, 50.0

    def score_of(value):
        if higher_is_better:
            return 100 * (value - worst) / (best - worst)
        return 100 * (worst - value) / (worst - best)

    return score_of(human_value), score_of(ai_value)


def compute_scores_for_task(conn, task_id, weights=None, difficulty=None):
    """
    Full pipeline for one task (optionally one difficulty segment):
    fetch averages -> normalize -> weighted score. Returns None if
    there's not enough data.
    """
    weights = weights or DEFAULT_WEIGHTS

    averages = get_task_averages(conn, task_id, difficulty=difficulty)
    if averages is None:
        return None

    h, a = averages["human"], averages["ai"]

    cost_h, cost_a = normalize_pair(h["cost"], a["cost"], higher_is_better=False)
    time_h, time_a = normalize_pair(h["time"], a["time"], higher_is_better=False)
    qual_h, qual_a = normalize_pair(h["quality"], a["quality"], higher_is_better=True)

    human_final = weights["cost"] * cost_h + weights["time"] * time_h + weights["quality"] * qual_h
    ai_final = weights["cost"] * cost_a + weights["time"] * time_a + weights["quality"] * qual_a

    return {
        "raw_averages": averages,
        "normalized_scores": {
            "human": {"cost": cost_h, "time": time_h, "quality": qual_h},
            "ai": {"cost": cost_a, "time": time_a, "quality": qual_a},
        },
        "final_scores": {
            "human": round(human_final, 2),
            "ai": round(ai_final, 2),
        },
    }


def compute_scores_for_all_tasks(weights=None):
    """Convenience function: runs compute_scores_for_task() for every task (overall, not segmented)."""
    conn = sqlite3.connect(DB_PATH)
    tasks = conn.execute("SELECT id, name FROM tasks").fetchall()

    results = {}
    for task_id, name in tasks:
        results[name] = compute_scores_for_task(conn, task_id, weights)

    conn.close()
    return results


if __name__ == "__main__":
    all_results = compute_scores_for_all_tasks()

    for task_name, result in all_results.items():
        print(f"\n{'=' * 55}\nTASK: {task_name}\n{'=' * 55}")

        if result is None:
            print("  Not enough data for this task yet.")
            continue

        raw = result["raw_averages"]
        norm = result["normalized_scores"]
        final = result["final_scores"]

        print(f"  RAW AVERAGES")
        print(f"    Human -> time: {raw['human']['time']:.1f}s | cost: Rs.{raw['human']['cost']:.2f} | quality: {raw['human']['quality']:.1f}/10")
        print(f"    AI    -> time: {raw['ai']['time']:.1f}s | cost: Rs.{raw['ai']['cost']:.4f} | quality: {raw['ai']['quality']:.1f}/10")

        print(f"  NORMALIZED (0-100, higher = better)")
        print(f"    Human -> cost: {norm['human']['cost']:.1f} | time: {norm['human']['time']:.1f} | quality: {norm['human']['quality']:.1f}")
        print(f"    AI    -> cost: {norm['ai']['cost']:.1f} | time: {norm['ai']['time']:.1f} | quality: {norm['ai']['quality']:.1f}")

        print(f"  FINAL WEIGHTED SCORE (Cost 40% / Time 30% / Quality 30%)")
        print(f"    Human = {final['human']}")
        print(f"    AI    = {final['ai']}")
