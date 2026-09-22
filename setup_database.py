"""
setup_database.py

WHAT THIS FILE DOES:
1. Creates the SQLite database file at database/app.db
2. Runs schema.sql to create the 4 tables (if they don't exist yet)
3. Loads data/tasks.csv, data/human_data.csv, data/ai_data.csv into
   those tables using pandas

WHY SQLITE:
SQLite stores the whole database as a single file (app.db) -- no
separate database server to install or run. Perfect for an MVP.

Run this AFTER generate_sample_data.py (or after you've prepared
your own CSVs in the same format).
"""

import sqlite3
import pandas as pd
import os

DB_PATH = "database/app.db"
SCHEMA_PATH = "database/schema.sql"


def create_tables(conn):
    """Reads schema.sql and executes it to create the tables."""
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    print("Tables created (or already existed).")


def load_tasks(conn):
    """
    Loads tasks.csv into the tasks table.
    Returns a dictionary mapping task name -> task_id, e.g.
    {"customer_email": 1, "document_summary": 2, ...}
    We need this mapping because human_data.csv and ai_data.csv refer
    to tasks by NAME, but the database links rows using task_id (a number).
    """
    df = pd.read_csv("data/tasks.csv")

    # Clear existing rows first so re-running this script doesn't duplicate data
    conn.execute("DELETE FROM tasks")

    df.to_sql("tasks", conn, if_exists="append", index=False)
    conn.commit()

    # Build the name -> id lookup dictionary
    task_rows = conn.execute("SELECT id, name FROM tasks").fetchall()
    name_to_id = {name: task_id for (task_id, name) in task_rows}
    print(f"Loaded {len(name_to_id)} tasks: {list(name_to_id.keys())}")
    return name_to_id


def load_human_data(conn, name_to_id):
    """Loads human_data.csv into the human_performance table."""
    df = pd.read_csv("data/human_data.csv")

    # Replace the "task" column (a name like "customer_email")
    # with "task_id" (a number) using our lookup dictionary
    df["task_id"] = df["task"].map(name_to_id)
    df = df.drop(columns=["task"])

    conn.execute("DELETE FROM human_performance")
    df.to_sql("human_performance", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Loaded {len(df)} human performance rows.")


def load_ai_data(conn, name_to_id):
    """Loads ai_data.csv into the ai_performance table."""
    df = pd.read_csv("data/ai_data.csv")

    df["task_id"] = df["task"].map(name_to_id)
    df = df.drop(columns=["task"])

    conn.execute("DELETE FROM ai_performance")
    df.to_sql("ai_performance", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Loaded {len(df)} AI performance rows.")


if __name__ == "__main__":
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    print(f"Connected to database at {DB_PATH}")

    create_tables(conn)
    name_to_id = load_tasks(conn)
    load_human_data(conn, name_to_id)
    load_ai_data(conn, name_to_id)

    conn.close()
    print("\nDatabase setup complete.")
