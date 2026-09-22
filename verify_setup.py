"""
verify_setup.py

WHAT THIS FILE DOES:
Connects to the database and prints out summary information, so you
can SEE with your own eyes that Phase 1 worked correctly:
  - How many tasks, human records, and AI records exist
  - Average time/cost/quality per task, for humans vs AI

This is just for checking our work -- it is NOT the comparison
engine (that comes in Phase 2). It's read-only and doesn't change
any data.
"""

import sqlite3

DB_PATH = "database/app.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 55)
print("DATABASE VERIFICATION")
print("=" * 55)

# --- Row counts ---
for table in ["tasks", "human_performance", "ai_performance", "task_results"]:
    count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:20s}: {count} rows")

print("\n" + "=" * 55)
print("PER-TASK AVERAGES (SAMPLE/SYNTHETIC DATA)")
print("=" * 55)

tasks = cur.execute("SELECT id, name, description FROM tasks").fetchall()

for task_id, name, description in tasks:
    print(f"\nTask: {name}  ({description})")

    # Human averages
    h_time, h_cost, h_quality = cur.execute(
        """SELECT AVG(time_seconds), AVG(labor_cost), AVG(quality_score)
           FROM human_performance WHERE task_id = ?""",
        (task_id,),
    ).fetchone()

    # AI averages
    a_time, a_cost, a_quality = cur.execute(
        """SELECT AVG(time_seconds), AVG(api_cost), AVG(quality_score)
           FROM ai_performance WHERE task_id = ?""",
        (task_id,),
    ).fetchone()

    print(f"  HUMAN -> avg time: {h_time:7.1f} sec | avg cost: Rs.{h_cost:6.2f} | avg quality: {h_quality:.1f}/10")
    print(f"  AI    -> avg time: {a_time:7.1f} sec | avg cost: Rs.{a_cost:6.4f} | avg quality: {a_quality:.1f}/10")

conn.close()

print("\n" + "=" * 55)
print("If you see numbers above (not errors), Phase 1 works correctly.")
print("=" * 55)
