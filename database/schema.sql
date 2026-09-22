-- schema.sql
-- This file defines the structure (tables) of our database.

-- TASKS: the list of business tasks we are analyzing
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT
);

-- HUMAN_PERFORMANCE: one row = one human worker doing one task once.
--
-- QUALITY IS NOW A RUBRIC, NOT ONE MAGIC NUMBER.
-- Instead of a single "how good was it" guess, quality is broken into
-- 4 named sub-criteria (each 1-10). quality_score is their average,
-- computed automatically when a row is inserted -- it is never entered
-- directly. This means every quality number can be explained by
-- pointing to what it's actually made of, instead of just asserting it.
--
-- DIFFICULTY marks whether this was a routine or complex instance of
-- the task. Real task volume is long-tailed: mostly routine, with a
-- smaller share of harder cases. Splitting on this lets the system
-- recommend differently per segment (e.g. AI for routine, Human or
-- Hybrid for complex) instead of one flat answer for the whole task.
CREATE TABLE IF NOT EXISTS human_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    worker_id TEXT,
    difficulty TEXT NOT NULL DEFAULT 'routine',   -- 'routine' or 'complex'
    time_seconds REAL,
    labor_cost REAL,
    quality_accuracy REAL,       -- 1-10: is the output factually/procedurally correct?
    quality_completeness REAL,   -- 1-10: does it cover everything the task required?
    quality_clarity REAL,        -- 1-10: is it clear, well-organized, easy to use?
    quality_consistency REAL,    -- 1-10: would it hold up the same way across similar cases?
    quality_score REAL,          -- average of the 4 criteria above (computed, not entered)
    notes TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- AI_PERFORMANCE: one row = one AI model doing one task once. Same
-- rubric + difficulty design as human_performance, for a fair comparison.
CREATE TABLE IF NOT EXISTS ai_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    model_name TEXT,
    difficulty TEXT NOT NULL DEFAULT 'routine',
    time_seconds REAL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    api_cost REAL,
    quality_accuracy REAL,
    quality_completeness REAL,
    quality_clarity REAL,
    quality_consistency REAL,
    quality_score REAL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- TASK_RESULTS: stores the outcome each time Analysis is run.
-- "segment" records whether this result is the overall (blended) view
-- or one difficulty segment ('overall', 'routine', 'complex').
CREATE TABLE IF NOT EXISTS task_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    segment TEXT DEFAULT 'overall',
    human_score REAL,
    ai_score REAL,
    recommendation TEXT,
    estimated_savings REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
