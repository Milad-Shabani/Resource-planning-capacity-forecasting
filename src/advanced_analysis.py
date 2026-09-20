"""
Advanced analysis — new outputs added on top of the original pipeline.

These surface analytical value that was already latent in the existing
data/model but not yet reported as its own decision-ready output:

  1. On-Time Delivery Rate (Service Level) — the forecast output already
     splits delivered volume into "same-day" vs. "deferred from a closed
     day" at the row level, but nothing previously rolled this up into a
     network/DC-level service-level metric. This does exactly that.

  2. Staff Reallocation Plan — the original pipeline identifies at-risk and
     surplus DCs separately but stops short of pairing them into an actual
     transfer recommendation. This greedily matches each at-risk DC with
     the best-fitting surplus DC of the same Service Type (falling back to
     any surplus DC) and quantifies a suggested shift transfer.

  3. Backtest Daily Trend — the original backtest only reports aggregate
     accuracy metrics (MAE/WAPE/etc.). This adds the day-by-day
     actual-vs-predicted series the aggregate metrics were computed from,
     so it can be charted directly instead of only tabulated.

  4. Multi-DC What-If Comparison — the original scenario analysis runs one
     capacity-expansion scenario for a single hand-picked DC. This runs the
     same scenario for the top N at-risk DCs and ranks them by net economic
     benefit, turning "a scenario" into "a prioritized investment list."

Author: Milad Shabani
"""
from typing import List

import numpy as np
import pandas as pd

from . import config
from .scenario_analysis import run_capacity_expansion_scenario


# ----------------------------------------------------------------------
# 1. ON-TIME DELIVERY RATE (SERVICE LEVEL)
# ----------------------------------------------------------------------
def on_time_delivery_rate(fc: pd.DataFrame) -> pd.DataFrame:
    """Network-wide and per-DC share of delivered demand that was fulfilled
    same-day vs. deferred from a previously closed/over-capacity day.
    """
    fc = fc.copy()
    fc["total_demand_component"] = fc["Of Which: Same-Day Demand"] + fc["Of Which: Deferred From Closed Day(s)"]

    by_dc = fc.groupby(["DC ID", "DC Name", "Service Type", "State"]).agg(
        same_day=("Of Which: Same-Day Demand", "sum"),
        deferred=("Of Which: Deferred From Closed Day(s)", "sum"),
        delivered_items=("Forecast Delivered Items", "sum"),
    ).reset_index()
    by_dc["total_component"] = by_dc["same_day"] + by_dc["deferred"]
    by_dc["on_time_rate"] = np.where(
        by_dc["total_component"] > 0, by_dc["same_day"] / by_dc["total_component"], np.nan
    )
    by_dc = by_dc.sort_values("on_time_rate")

    network_same_day = fc["Of Which: Same-Day Demand"].sum()
    network_deferred = fc["Of Which: Deferred From Closed Day(s)"].sum()
    network_rate = network_same_day / (network_same_day + network_deferred)

    return by_dc[["DC ID", "DC Name", "Service Type", "State", "same_day", "deferred",
                   "delivered_items", "on_time_rate"]], network_rate


# ----------------------------------------------------------------------
# 2. STAFF REALLOCATION PLAN
# ----------------------------------------------------------------------
def staff_reallocation_plan(dc_monthly: pd.DataFrame) -> pd.DataFrame:
    """Greedily pair each at-risk DC with the best-fitting surplus DC
    (same Service Type preferred) and recommend a shift transfer sized to
    close roughly half the gap between them -- a conservative first move,
    not a full rebalancing in one step.
    """
    at_risk = dc_monthly[dc_monthly["pct_days_high_risk"] >= config.AT_RISK_DAY_SHARE_THRESHOLD].copy()
    surplus = dc_monthly[dc_monthly["pct_days_surplus"] >= config.SURPLUS_DAY_SHARE_THRESHOLD].copy()

    if at_risk.empty or surplus.empty:
        return pd.DataFrame(columns=[
            "At-Risk DC", "At-Risk Utilization", "Donor DC", "Donor Utilization",
            "Donor Service Type Match", "Suggested Shift Transfer", "Rationale",
        ])

    surplus_pool = surplus.copy()
    rows = []
    for _, risk_row in at_risk.sort_values("avg_utilization", ascending=False).iterrows():
        if surplus_pool.empty:
            break
        same_type = surplus_pool[surplus_pool["Service Type"] == risk_row["Service Type"]]
        candidates = same_type if not same_type.empty else surplus_pool
        donor = candidates.sort_values("avg_utilization").iloc[0]

        # Suggested transfer: half the average daily staff gap between the
        # two DCs, floored at 1 shift -- a conservative rebalancing step.
        gap = max(risk_row["total_staff_needed"] - donor["total_staff_needed"], 0) / max(risk_row["active_days"], 1)
        suggested_shift = max(1, int(round(gap * 0.5)))

        rows.append(dict(
            **{"At-Risk DC": risk_row["DC Name"], "At-Risk Utilization": risk_row["avg_utilization"],
               "Donor DC": donor["DC Name"], "Donor Utilization": donor["avg_utilization"],
               "Donor Service Type Match": "Yes" if not same_type.empty else "No (nearest available)",
               "Suggested Shift Transfer": suggested_shift,
               "Rationale": f"{risk_row['DC Name']} runs at {risk_row['avg_utilization']*100:.0f}% avg. "
                            f"utilization vs. {donor['DC Name']} at {donor['avg_utilization']*100:.0f}%; "
                            f"moving ~{suggested_shift} shift(s)/day narrows the gap without over-correcting."}
        ))
        surplus_pool = surplus_pool[surplus_pool["DC Name"] != donor["DC Name"]]

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 3. BACKTEST DAILY TREND
# ----------------------------------------------------------------------
def backtest_daily_trend(bt: pd.DataFrame) -> pd.DataFrame:
    """Network-wide actual vs. capacity-constrained predicted orders/items,
    by day -- the time series the aggregate backtest metrics summarize.
    """
    daily = bt.groupby("DateNorm").agg(
        Actual_Items=("Items", "sum"),
        Predicted_Items=("capped_pred_items", "sum"),
        Actual_Orders=("Orders", "sum"),
        Predicted_Orders=("pred_orders", "sum"),
    ).reset_index().rename(columns={"DateNorm": "Date"})
    daily["Items_Abs_Error_Pct"] = (
        (daily["Predicted_Items"] - daily["Actual_Items"]).abs() / daily["Actual_Items"].replace(0, np.nan)
    ) * 100
    return daily.sort_values("Date")


# ----------------------------------------------------------------------
# 4. MULTI-DC WHAT-IF COMPARISON
# ----------------------------------------------------------------------
def multi_dc_scenario_comparison(artifacts, at_risk_dcs: pd.DataFrame, top_n: int = 3,
                                   capacity_multiplier: float = 1.5) -> pd.DataFrame:
    """Run the capacity-expansion scenario for the top N at-risk DCs and
    rank them by net economic benefit -- turns a single what-if into a
    prioritized capital-investment shortlist.
    """
    targets = at_risk_dcs.sort_values("pct_days_high_risk", ascending=False).head(top_n)
    rows = []
    for _, row in targets.iterrows():
        dc_name = row["DC Name"]
        scenario = run_capacity_expansion_scenario(artifacts, dc_name, capacity_multiplier=capacity_multiplier)
        detail = scenario["detail"]
        rows.append(dict(
            **{"DC Name": dc_name, "Service Type": row["Service Type"], "State": row["State"],
               "Pre-Scenario Avg. Utilization": row["avg_utilization"],
               "Extra Items Delivered": int(detail["Delta Delivered Items"].sum()),
               "Extra Staff Shifts": int(detail["Delta Staff Shifts"].sum()),
               "Extra Revenue": scenario["cost_benefit"].iloc[0, 1],
               "Extra Cost": scenario["cost_benefit"].iloc[1, 1],
               "Net Benefit": scenario["cost_benefit"].iloc[2, 1]}
        ))
    return pd.DataFrame(rows).sort_values("Net Benefit", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------
# 5. NETWORK SUMMARY BY REGION (STATE)
# ----------------------------------------------------------------------
def region_summary(dc_monthly: pd.DataFrame) -> pd.DataFrame:
    reg = dc_monthly.groupby("State").agg(
        DC_Count=("DC ID", "count"),
        Avg_Utilization=("avg_utilization", "mean"),
        Total_Staff_Needed=("total_staff_needed", "sum"),
        DCs_At_Risk=("pct_days_high_risk", lambda s: (s >= config.AT_RISK_DAY_SHARE_THRESHOLD).sum()),
        DCs_Surplus=("pct_days_surplus", lambda s: (s >= config.SURPLUS_DAY_SHARE_THRESHOLD).sum()),
    ).reset_index()
    return reg.sort_values("Avg_Utilization", ascending=False)
