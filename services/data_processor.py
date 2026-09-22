"""
data_processor.py

WHAT THIS FILE DOES:
Handles CSV uploads for human and AI performance data: validates
columns and numeric values, finds/creates the task, and inserts rows.

WHAT CHANGED FROM THE FIRST VERSION:
CSVs now use the rubric format (4 quality sub-criteria instead of one
quality_score column) plus a difficulty column ('routine'/'complex').
quality_score is computed automatically as the average of the 4
sub-criteria at insert time -- it is never accepted as raw input, so
it can never be entered inconsistently with what it's supposed to represent.
"""

import pandas as pd

HUMAN_COLUMNS = [
    "task", "worker_id", "difficulty", "time_seconds", "labor_cost",
    "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency",
]
AI_COLUMNS = [
    "task", "model_name", "difficulty", "time_seconds", "input_tokens", "output_tokens", "api_cost",
    "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency",
]

HUMAN_NUMERIC_COLUMNS = ["time_seconds", "labor_cost", "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency"]
AI_NUMERIC_COLUMNS = ["time_seconds", "input_tokens", "output_tokens", "api_cost", "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency"]

QUALITY_COLUMNS = ["quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency"]
VALID_DIFFICULTIES = {"routine", "complex"}


class CSVValidationError(Exception):
    """Raised when an uploaded CSV doesn't match the expected format."""
    pass


def _validate_columns(df, expected_columns, kind):
    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        raise CSVValidationError(
            f"{kind} CSV is missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(expected_columns)}"
        )


def _validate_numeric(df, numeric_columns, kind):
    for col in numeric_columns:
        non_numeric = pd.to_numeric(df[col], errors="coerce").isna()
        if non_numeric.any():
            bad_rows = df.index[non_numeric].tolist()
            raise CSVValidationError(f"{kind} CSV column '{col}' has non-numeric value(s) in row(s): {bad_rows}")


def _validate_quality_range(df, kind):
    for col in QUALITY_COLUMNS:
        out_of_range = ~df[col].between(1, 10)
        if out_of_range.any():
            bad_rows = df.index[out_of_range].tolist()
            raise CSVValidationError(f"{kind} CSV column '{col}' must be between 1 and 10 (row(s): {bad_rows})")


def _validate_difficulty(df, kind):
    invalid = ~df["difficulty"].isin(VALID_DIFFICULTIES)
    if invalid.any():
        bad_rows = df.index[invalid].tolist()
        raise CSVValidationError(
            f"{kind} CSV column 'difficulty' must be 'routine' or 'complex' (row(s): {bad_rows})"
        )


def _get_or_create_task(conn, task_name):
    row = conn.execute("SELECT id FROM tasks WHERE name = ?", (task_name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO tasks (name, description, category) VALUES (?, ?, ?)",
        (task_name, f"Uploaded task: {task_name}", "Uncategorized"),
    )
    conn.commit()
    return cur.lastrowid


def process_human_csv(conn, filepath_or_buffer):
    """Validates and inserts a human performance CSV. Returns rows inserted."""
    df = pd.read_csv(filepath_or_buffer)
    _validate_columns(df, HUMAN_COLUMNS, "Human")
    _validate_numeric(df, HUMAN_NUMERIC_COLUMNS, "Human")
    _validate_quality_range(df, "Human")
    _validate_difficulty(df, "Human")

    inserted = 0
    for _, row in df.iterrows():
        task_id = _get_or_create_task(conn, str(row["task"]).strip())
        quality_score = round(sum(float(row[c]) for c in QUALITY_COLUMNS) / len(QUALITY_COLUMNS), 2)
        conn.execute(
            """INSERT INTO human_performance
               (task_id, worker_id, difficulty, time_seconds, labor_cost,
                quality_accuracy, quality_completeness, quality_clarity, quality_consistency, quality_score, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, row["worker_id"], row["difficulty"], float(row["time_seconds"]), float(row["labor_cost"]),
             float(row["quality_accuracy"]), float(row["quality_completeness"]),
             float(row["quality_clarity"]), float(row["quality_consistency"]), quality_score, ""),
        )
        inserted += 1

    conn.commit()
    return inserted


def process_ai_csv(conn, filepath_or_buffer):
    """Validates and inserts an AI performance CSV. Returns rows inserted."""
    df = pd.read_csv(filepath_or_buffer)
    _validate_columns(df, AI_COLUMNS, "AI")
    _validate_numeric(df, AI_NUMERIC_COLUMNS, "AI")
    _validate_quality_range(df, "AI")
    _validate_difficulty(df, "AI")

    inserted = 0
    for _, row in df.iterrows():
        task_id = _get_or_create_task(conn, str(row["task"]).strip())
        quality_score = round(sum(float(row[c]) for c in QUALITY_COLUMNS) / len(QUALITY_COLUMNS), 2)
        conn.execute(
            """INSERT INTO ai_performance
               (task_id, model_name, difficulty, time_seconds, input_tokens, output_tokens, api_cost,
                quality_accuracy, quality_completeness, quality_clarity, quality_consistency, quality_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, row["model_name"], row["difficulty"], float(row["time_seconds"]),
             int(row["input_tokens"]), int(row["output_tokens"]), float(row["api_cost"]),
             float(row["quality_accuracy"]), float(row["quality_completeness"]),
             float(row["quality_clarity"]), float(row["quality_consistency"]), quality_score),
        )
        inserted += 1

    conn.commit()
    return inserted
