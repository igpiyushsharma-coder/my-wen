"""
recommendation_engine.py

WHAT THIS FILE DOES:
Takes comparison_engine's output and turns it into a decision:
    HUMAN RECOMMENDED / AI RECOMMENDED / HYBRID RECOMMENDED / INSUFFICIENT_DATA

WHAT CHANGED FROM THE FIRST VERSION:
1. Every recommendation can now be computed for a specific difficulty
   segment ('routine' or 'complex'), not just the whole task blended
   together. build_segmented_recommendations() returns both segments
   for a task in one call, which is what lets the system say something
   more useful than one flat answer -- e.g. "AI for routine emails,
   Human for complex ones" instead of just "AI for customer_email."
2. Each result now includes a quality_breakdown: the 4 rubric
   sub-scores behind the average, so "AI quality is too low" can be
   explained by which specific criteria are weak, not just asserted.

DECISION LOGIC (unchanged in structure):
1. If neither side clears the minimum quality threshold -> INSUFFICIENT_DATA
2. If only one side clears it -> that side wins automatically (quality
   is a hard gate, not just a weighted factor)
3. If both clear it -> compare weighted efficiency scores; HYBRID when
   they're close, or when AI wins on score but human quality is
   notably higher (AI drafts, human reviews).
"""

try:
    from services.comparison_engine import (
        compute_scores_for_task, get_quality_breakdown, get_available_difficulties,
    )
except ImportError:
    from comparison_engine import (
        compute_scores_for_task, get_quality_breakdown, get_available_difficulties,
    )

CLOSE_SCORE_MARGIN = 10.0
QUALITY_GAP_FOR_HYBRID = 1.0


def _pct_lower(a, b):
    """How much lower `a` is than `b`, as a percentage of `b`."""
    if b == 0:
        return 0.0
    return round(100 * (b - a) / b, 1)


def build_recommendation(task_id, task_name, conn, weights=None, min_quality=7.0, difficulty=None):
    """
    Runs comparison + decision logic for one task, optionally scoped
    to one difficulty segment. Returns raw numbers, scores, the
    quality rubric breakdown, the recommendation, and a plain-English
    explanation grounded in the actual figures.
    """
    comparison = compute_scores_for_task(conn, task_id, weights, difficulty=difficulty)

    if comparison is None:
        return {
            "task_name": task_name,
            "difficulty": difficulty,
            "recommendation": "INSUFFICIENT_DATA",
            "explanation": "There isn't enough recorded data for this task/segment yet.",
            "raw_averages": None,
            "final_scores": None,
            "quality_breakdown": None,
        }

    h = comparison["raw_averages"]["human"]
    a = comparison["raw_averages"]["ai"]
    human_score = comparison["final_scores"]["human"]
    ai_score = comparison["final_scores"]["ai"]
    quality_breakdown = get_quality_breakdown(conn, task_id, difficulty=difficulty)

    human_ok = h["quality"] >= min_quality
    ai_ok = a["quality"] >= min_quality

    cost_pct = _pct_lower(a["cost"], h["cost"])
    time_pct = _pct_lower(a["time"], h["time"])

    if not human_ok and not ai_ok:
        recommendation = "INSUFFICIENT_DATA"
        explanation = (
            f"Neither Human (quality {h['quality']:.1f}/10) nor AI (quality {a['quality']:.1f}/10) "
            f"meets the minimum required quality threshold of {min_quality:.1f}/10. "
            f"Collect more data or improve the process before relying on either option."
        )

    elif ai_ok and not human_ok:
        recommendation = "AI RECOMMENDED"
        explanation = (
            f"AI recommended because it meets the minimum quality threshold ({a['quality']:.1f}/10 >= "
            f"{min_quality:.1f}/10) while Human performance does not ({h['quality']:.1f}/10)."
        )

    elif human_ok and not ai_ok:
        recommendation = "HUMAN RECOMMENDED"
        explanation = (
            f"Human recommended because AI quality ({a['quality']:.1f}/10) falls below the minimum "
            f"required threshold ({min_quality:.1f}/10), even though AI is {cost_pct}% cheaper and "
            f"{time_pct}% faster on average."
        )
        if quality_breakdown:
            weak = min(quality_breakdown["ai"], key=quality_breakdown["ai"].get)
            explanation += f" AI's weakest rubric criterion here is {weak} ({quality_breakdown['ai'][weak]}/10)."

    else:
        score_gap = abs(ai_score - human_score)
        quality_gap = h["quality"] - a["quality"]

        if ai_score > human_score and quality_gap >= QUALITY_GAP_FOR_HYBRID:
            recommendation = "HYBRID RECOMMENDED"
            explanation = (
                f"Hybrid recommended: AI is {cost_pct}% cheaper and {time_pct}% faster, but Human "
                f"quality ({h['quality']:.1f}/10) is noticeably higher than AI quality ({a['quality']:.1f}/10). "
                f"Using AI for a first draft with human review captures AI's speed/cost while protecting quality."
            )
        elif score_gap <= CLOSE_SCORE_MARGIN:
            recommendation = "HYBRID RECOMMENDED"
            explanation = (
                f"Hybrid recommended: Human (score {human_score:.1f}) and AI (score {ai_score:.1f}) are "
                f"too close to confidently pick one side. A hybrid workflow captures AI's cost/time "
                f"advantage while keeping human oversight."
            )
        elif ai_score > human_score:
            recommendation = "AI RECOMMENDED"
            explanation = (
                f"AI recommended because it is {cost_pct}% cheaper and {time_pct}% faster while maintaining "
                f"the required quality threshold (AI quality: {a['quality']:.1f}/10 vs required {min_quality:.1f}/10)."
            )
        else:
            recommendation = "HUMAN RECOMMENDED"
            explanation = (
                f"Human recommended: despite AI being {cost_pct}% cheaper and {time_pct}% faster, Human's "
                f"overall efficiency score ({human_score:.1f}) is higher once quality is weighted in."
            )

    return {
        "task_name": task_name,
        "difficulty": difficulty,
        "recommendation": recommendation,
        "explanation": explanation,
        "raw_averages": comparison["raw_averages"],
        "final_scores": comparison["final_scores"],
        "quality_breakdown": quality_breakdown,
    }


def build_segmented_recommendations(task_id, task_name, conn, weights=None, min_quality=7.0):
    """
    Returns a dict of {difficulty: recommendation_result} for every
    difficulty segment that has data for this task -- e.g.
    {'routine': {...}, 'complex': {...}}. This is what powers the
    "AI for routine, Human/Hybrid for complex" view instead of one
    flat answer per task.
    """
    segments = {}
    for difficulty in get_available_difficulties(conn, task_id):
        segments[difficulty] = build_recommendation(
            task_id, task_name, conn, weights=weights, min_quality=min_quality, difficulty=difficulty,
        )
    return segments


if __name__ == "__main__":
    import sqlite3

    conn = sqlite3.connect("database/app.db")
    tasks = conn.execute("SELECT id, name FROM tasks").fetchall()

    for task_id, name in tasks:
        print(f"\n{'=' * 55}\nTASK: {name} (overall, blended)\n{'=' * 55}")
        overall = build_recommendation(task_id, name, conn)
        print(f"  {overall['recommendation']}")
        print(f"  {overall['explanation']}")

        segments = build_segmented_recommendations(task_id, name, conn)
        for difficulty, result in segments.items():
            print(f"\n  --- {difficulty} segment ---")
            print(f"  {result['recommendation']}")
            print(f"  {result['explanation']}")

    conn.close()
