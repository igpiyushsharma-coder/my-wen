"""
ai_service.py

WHAT THIS FILE DOES:
This is a STUB for optional live AI API integration (Phase 8 in the
original plan). It is NOT called anywhere in app.py -- the app runs
entirely on Demo Mode data (sample CSVs + your own uploads) by design,
so it always works without an internet connection or API key.

If you want to extend this into a real integration later, this shows
the shape of it: call a chat-completion API, time it, measure tokens,
calculate cost from config.py pricing, and return a row shaped like
one line of ai_data.csv.

WHY THIS IS SEPARATE FROM THE MAIN APP:
Keeping this isolated means a missing/invalid API key or a network
hiccup can never break the core dashboard -- it can only affect this
one optional feature if you choose to wire it into a route later.
"""

import os
import time

# Reads the key from an environment variable -- never hardcode a key
# in source code. Copy .env.example to .env and fill it in if you
# want to try this.
API_KEY = os.environ.get("AI_API_KEY")


def is_configured():
    """Returns True if an API key is available in the environment."""
    return bool(API_KEY)


def run_live_ai_task(prompt, model_name="Model-A"):
    """
    Example of what a real integration would look like. This function
    is NOT wired into any Flask route currently -- it's here as a
    documented starting point.

    Returns a dict shaped like one row of ai_data.csv, so it could be
    inserted into ai_performance the same way process_ai_csv() does.
    """
    if not is_configured():
        raise RuntimeError(
            "No AI_API_KEY found in environment. Set it in a .env file "
            "(see .env.example) to use live API integration. The app "
            "works fine without this -- it just uses sample/uploaded data instead."
        )

    # --- This is where a real API call would go, e.g.: ---
    #
    # import requests
    # start = time.time()
    # response = requests.post(
    #     "https://api.openai.com/v1/chat/completions",
    #     headers={"Authorization": f"Bearer {API_KEY}"},
    #     json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]},
    # )
    # elapsed = time.time() - start
    # result = response.json()
    # input_tokens = result["usage"]["prompt_tokens"]
    # output_tokens = result["usage"]["completion_tokens"]
    #
    # Then calculate api_cost using the pricing in config.py's
    # ai_pricing dict, the same way generate_sample_data.py does it.

    raise NotImplementedError(
        "Live API integration is not implemented in this MVP -- see the "
        "comments in this function for how to add it."
    )
