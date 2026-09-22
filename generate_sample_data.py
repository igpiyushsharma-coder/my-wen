import csv
import random

random.seed(42)

# -----------------------------------------------------------------
# 1. TASKS
# -----------------------------------------------------------------
TASKS = [
    {"name": "customer_email", "description": "Replying to a routine customer support email", "category": "Customer Support"},
    {"name": "document_summary", "description": "Summarizing a business document into key points", "category": "Content Processing"},
    {"name": "data_extraction", "description": "Extracting structured fields (names, dates, amounts) from a document", "category": "Data Entry"},
]

DIFFICULTIES = ["routine", "complex"]
ROUTINE_SHARE = 0.7  # ~70% of real-world volume is the routine case

# -----------------------------------------------------------------
# 2. TIME / COST RANGES, per task and difficulty
#    Complex cases take longer and cost more for both sides.
# -----------------------------------------------------------------
HUMAN_RANGES = {
    ("customer_email", "routine"):   {"time": (200, 420), "cost": (8, 16)},
    ("customer_email", "complex"):   {"time": (420, 720), "cost": (16, 30)},
    ("document_summary", "routine"): {"time": (250, 550), "cost": (16, 28)},
    ("document_summary", "complex"): {"time": (550, 1100), "cost": (28, 55)},
    ("data_extraction", "routine"):  {"time": (150, 350), "cost": (6, 14)},
    ("data_extraction", "complex"):  {"time": (350, 650), "cost": (14, 28)},
}

AI_RANGES = {
    ("customer_email", "routine"):   {"time": (2, 5),  "input_tokens": (350, 600),  "output_tokens": (120, 250)},
    ("customer_email", "complex"):   {"time": (4, 8),  "input_tokens": (700, 1100), "output_tokens": (250, 450)},
    ("document_summary", "routine"): {"time": (3, 7),  "input_tokens": (1000, 1800), "output_tokens": (180, 350)},
    ("document_summary", "complex"): {"time": (6, 13), "input_tokens": (2000, 3200), "output_tokens": (350, 600)},
    ("data_extraction", "routine"):  {"time": (2, 4),  "input_tokens": (400, 900),  "output_tokens": (60, 150)},
    ("data_extraction", "complex"):  {"time": (4, 9),  "input_tokens": (1000, 1800), "output_tokens": (150, 300)},
}

# -----------------------------------------------------------------
# 3. QUALITY RANGES (per sub-criterion), per task and difficulty.
#    This is the key modeling choice: AI quality drops noticeably on
#    complex cases; human quality drops too, but less sharply. This
#    mirrors a well-documented real pattern (AI handles routine,
#    well-templated cases well, but degrades on ambiguous/edge cases)
#    and is what makes the segmented recommendation meaningful.
# -----------------------------------------------------------------
HUMAN_QUALITY_RANGES = {
    ("customer_email", "routine"):   (7, 10),
    ("customer_email", "complex"):   (6, 9),
    ("document_summary", "routine"): (7, 9),
    ("document_summary", "complex"): (6, 9),
    ("data_extraction", "routine"):  (7, 9),
    ("data_extraction", "complex"):  (6, 8),
}

AI_QUALITY_RANGES = {
    ("customer_email", "routine"):   (7, 9),
    ("customer_email", "complex"):   (4, 7),
    ("document_summary", "routine"): (7, 9),
    ("document_summary", "complex"): (4, 7),
    ("data_extraction", "routine"):  (7, 9),
    ("data_extraction", "complex"):  (5, 7),
}

QUALITY_CRITERIA = ["quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency"]

AI_MODELS = {
    "Model-A": {"price_per_1k_input": 0.05, "price_per_1k_output": 0.15},
    "Model-B": {"price_per_1k_input": 0.08, "price_per_1k_output": 0.24},
}

NUM_HUMAN_WORKERS_PER_TASK = 20
RUNS_PER_MODEL_PER_DIFFICULTY = 5


def make_quality_scores(quality_range):
    """
    Draws 4 independent sub-criterion scores from the given (min, max)
    range, then returns (scores_dict, average). Independent draws mean
    the average isn't just one number repeated 4 times -- some natural
    variation between criteria, like real evaluation would show.
    """
    scores = {c: random.randint(*quality_range) for c in QUALITY_CRITERIA}
    avg = round(sum(scores.values()) / len(scores), 2)
    return scores, avg


def split_worker_count(total, routine_share):
    """Splits a worker count into (routine_count, complex_count)."""
    routine_count = round(total * routine_share)
    return routine_count, total - routine_count


def generate_human_rows():
    rows = []
    for task in TASKS:
        name = task["name"]
        routine_n, complex_n = split_worker_count(NUM_HUMAN_WORKERS_PER_TASK, ROUTINE_SHARE)
        worker_num = 1
        for difficulty, count in [("routine", routine_n), ("complex", complex_n)]:
            ranges = HUMAN_RANGES[(name, difficulty)]
            qrange = HUMAN_QUALITY_RANGES[(name, difficulty)]
            for _ in range(count):
                worker_id = f"H{worker_num:02d}"
                worker_num += 1
                time_seconds = random.randint(*ranges["time"])
                labor_cost = round(random.uniform(*ranges["cost"]), 2)
                scores, avg = make_quality_scores(qrange)
                rows.append([
                    name, worker_id, difficulty, time_seconds, labor_cost,
                    scores["quality_accuracy"], scores["quality_completeness"],
                    scores["quality_clarity"], scores["quality_consistency"], avg,
                ])
    return rows


def generate_ai_rows():
    rows = []
    for task in TASKS:
        name = task["name"]
        for difficulty in DIFFICULTIES:
            ranges = AI_RANGES[(name, difficulty)]
            qrange = AI_QUALITY_RANGES[(name, difficulty)]
            for model_name, pricing in AI_MODELS.items():
                for _ in range(RUNS_PER_MODEL_PER_DIFFICULTY):
                    time_seconds = round(random.uniform(*ranges["time"]), 2)
                    input_tokens = random.randint(*ranges["input_tokens"])
                    output_tokens = random.randint(*ranges["output_tokens"])
                    api_cost = round(
                        (input_tokens / 1000) * pricing["price_per_1k_input"]
                        + (output_tokens / 1000) * pricing["price_per_1k_output"], 4,
                    )
                    scores, avg = make_quality_scores(qrange)
                    rows.append([
                        name, model_name, difficulty, time_seconds, input_tokens, output_tokens, api_cost,
                        scores["quality_accuracy"], scores["quality_completeness"],
                        scores["quality_clarity"], scores["quality_consistency"], avg,
                    ])
    return rows


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows -> {path}")


if __name__ == "__main__":
    print("Generating SAMPLE/SYNTHETIC data (rubric-based quality, routine/complex segments)...")

    write_csv(
        "data/tasks.csv",
        ["name", "description", "category"],
        [[t["name"], t["description"], t["category"]] for t in TASKS],
    )

    write_csv(
        "data/human_data.csv",
        ["task", "worker_id", "difficulty", "time_seconds", "labor_cost",
         "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency", "quality_score"],
        generate_human_rows(),
    )

    write_csv(
        "data/ai_data.csv",
        ["task", "model_name", "difficulty", "time_seconds", "input_tokens", "output_tokens", "api_cost",
         "quality_accuracy", "quality_completeness", "quality_clarity", "quality_consistency", "quality_score"],
        generate_ai_rows(),
    )

    print("Done. All data in this project is SAMPLE/SYNTHETIC data for demo purposes only.")
