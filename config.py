"""
config.py

WHAT THIS FILE DOES:
Holds all the "tunable knobs" of the system in one place:
  - scoring weights (cost/time/quality)
  - minimum quality threshold
  - AI model pricing (per 1,000 tokens)
  - default assumed monthly volume (used on the dashboard before a
    user has entered a task-specific volume)

Settings are persisted to settings.json so changes made on the
Settings page survive a server restart. If settings.json doesn't
exist yet (first run), we fall back to these defaults and create it.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULTS = {
    "weights": {
        "cost": 0.40,
        "time": 0.30,
        "quality": 0.30,
    },
    "min_quality_threshold": 7.0,
    "default_monthly_volume": 5000,
    "ai_pricing": {
        "Model-A": {"price_per_1k_input": 0.05, "price_per_1k_output": 0.15},
        "Model-B": {"price_per_1k_input": 0.08, "price_per_1k_output": 0.24},
    },
}


def load_settings():
    """Loads settings.json, creating it with defaults if it doesn't exist."""
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()

    with open(SETTINGS_PATH, "r") as f:
        return json.load(f)


def save_settings(settings_dict):
    """Writes the given settings dictionary to settings.json."""
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings_dict, f, indent=2)
