"""
cost_calculator.py

WHAT THIS FILE DOES:
Projects monthly/yearly savings for a task from its average human/AI
cost and time, multiplied by a volume the user supplies.

WHAT CHANGED FROM THE FIRST VERSION:
The original version only returned one point-estimate savings number
(e.g. "Rs.172,350/month"), which presents an estimate as if it were a
certainty. calculate_savings_with_confidence() instead takes the
individual cost values behind each average (not just the average
itself) and returns a range, based on how much those values actually
varied in the sample data. A wide range is itself useful information
-- it means the estimate is less certain and probably needs more data.

HOW THE RANGE IS COMPUTED (explained simply):
For each side (human, AI), we compute the average cost AND how much
individual costs typically differed from that average (the standard
deviation). We then combine both sides' variability to get a savings
range: pessimistic (human cheaper than usual, AI pricier than usual)
and optimistic (the reverse). This assumes the two sides vary
independently of each other, which is a reasonable simplifying
assumption for an MVP -- documented here rather than hidden.
"""

import statistics


def calculate_savings(human_cost_per_task, ai_cost_per_task,
                       human_time_per_task_sec, ai_time_per_task_sec,
                       monthly_volume):
    """
    Point-estimate version (kept for simple call sites / backward
    compatibility): one monthly/yearly savings number from averages.
    """
    human_monthly_cost = human_cost_per_task * monthly_volume
    ai_monthly_cost = ai_cost_per_task * monthly_volume
    monthly_savings = human_monthly_cost - ai_monthly_cost
    yearly_savings = monthly_savings * 12

    human_monthly_time_hours = (human_time_per_task_sec * monthly_volume) / 3600
    ai_monthly_time_hours = (ai_time_per_task_sec * monthly_volume) / 3600
    time_saved_hours = human_monthly_time_hours - ai_monthly_time_hours

    return {
        "monthly_volume": monthly_volume,
        "human_monthly_cost": round(human_monthly_cost, 2),
        "ai_monthly_cost": round(ai_monthly_cost, 2),
        "monthly_savings": round(monthly_savings, 2),
        "yearly_savings": round(yearly_savings, 2),
        "human_monthly_time_hours": round(human_monthly_time_hours, 1),
        "ai_monthly_time_hours": round(ai_monthly_time_hours, 1),
        "time_saved_hours": round(time_saved_hours, 1),
    }


def calculate_savings_with_confidence(human_costs, ai_costs, human_times, ai_times, monthly_volume):
    """
    Range version: takes the RAW list of individual cost/time values
    behind each average (e.g. every human worker's labor_cost), and
    returns a savings range instead of a single number.

    human_costs / ai_costs / human_times / ai_times: lists of numbers
    (e.g. from comparison_engine.get_raw_cost_time()).
    """
    human_mean_cost = statistics.mean(human_costs)
    ai_mean_cost = statistics.mean(ai_costs)

    # pstdev needs at least 1 value; with only 1 value, variability is 0
    human_std_cost = statistics.pstdev(human_costs) if len(human_costs) > 1 else 0.0
    ai_std_cost = statistics.pstdev(ai_costs) if len(ai_costs) > 1 else 0.0

    point_estimate = calculate_savings(human_mean_cost, ai_mean_cost,
                                        statistics.mean(human_times), statistics.mean(ai_times),
                                        monthly_volume)

    # Combine variability from both sides (assumes independence -- a
    # simplifying assumption, documented above).
    per_task_savings_std = (human_std_cost ** 2 + ai_std_cost ** 2) ** 0.5
    monthly_savings_std = per_task_savings_std * monthly_volume

    monthly_savings_low = round(point_estimate["monthly_savings"] - monthly_savings_std, 2)
    monthly_savings_high = round(point_estimate["monthly_savings"] + monthly_savings_std, 2)

    point_estimate["monthly_savings_low"] = monthly_savings_low
    point_estimate["monthly_savings_high"] = monthly_savings_high
    point_estimate["yearly_savings_low"] = round(monthly_savings_low * 12, 2)
    point_estimate["yearly_savings_high"] = round(monthly_savings_high * 12, 2)
    point_estimate["sample_size"] = {"human_records": len(human_costs), "ai_records": len(ai_costs)}

    return point_estimate
