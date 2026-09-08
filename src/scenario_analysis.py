"""
What-if scenario analysis: simulate increasing the capacity of a chronic
bottleneck DC and quantify the network impact — extra items delivered, extra
staff shifts required, backlog reduction, and net economic value.
"""
from typing import Dict

import numpy as np
import pandas as pd

from . import config
from .date_utils import date_range, shift, weekday_name
from .forecasting import ForecastArtifacts, _items_per_order, _weekday_share


def run_capacity_expansion_scenario(
    artifacts: ForecastArtifacts,
    target_dc_name: str,
    capacity_multiplier: float = 1.5,
    start_date: str = None,
    horizon_days: int = None,
) -> Dict[str, pd.DataFrame]:
    start_date = start_date or config.FORECAST_START_DATE
    horizon_days = horizon_days or config.FORECAST_HORIZON_DAYS
    forecast_dates = date_range(start_date, horizon_days)

    target_dc_id = artifacts.roster.loc[artifacts.roster["DC Name"] == target_dc_name, "DC ID"].iloc[0]
    target_tss = artifacts.roster.loc[artifacts.roster["DC ID"] == target_dc_id, "TS"].unique()

    rows = []
    carry_over: Dict[tuple, float] = {}

    for d in forecast_dates:
        wd = weekday_name(d)
        for ts in target_tss:
            key = (target_dc_id, ts)
            cap_old = artifacts.capacity_lookup.get((target_dc_id, ts, wd), 0)
            cap_new = int(cap_old * capacity_multiplier)

            if cap_old == 0:
                rows.append((d, ts, cap_old, cap_new, 0, 0, 0, 0))
                continue

            lag = artifacts.lag_lookup.get(target_dc_id, 0)
            sale_date = shift(d, -lag)
            sale_items = artifacts.sale_lookup.get(sale_date, 0)

            own_items = _weekday_share(artifacts, target_dc_id, ts, wd) * sale_items
            deferred_in = carry_over.get(key, 0)
            requested = own_items + deferred_in

            ipo = _items_per_order(artifacts, target_dc_id, ts)

            delivered_old = int(round(min(requested, cap_old * ipo)))
            delivered_new = int(round(min(requested, cap_new * ipo)))
            carry_over[key] = max(0, requested - delivered_new)

            staff_old = int(np.ceil(delivered_old / config.ORDERS_PER_STAFF_PER_SHIFT)) if delivered_old > 0 else 0
            staff_new = int(np.ceil(delivered_new / config.ORDERS_PER_STAFF_PER_SHIFT)) if delivered_new > 0 else 0

            rows.append((d, ts, cap_old, cap_new, delivered_old, delivered_new, staff_old, staff_new))

    wi_df = pd.DataFrame(rows, columns=[
        "Delivery Date", "Time Scope", "Original Capacity", f"New Capacity ({int((capacity_multiplier-1)*100)}% Up)",
        "Original Delivered Items", "New Delivered Items", "Original Staff Needed", "New Staff Needed",
    ])
    wi_df["Delta Delivered Items"] = wi_df["New Delivered Items"] - wi_df["Original Delivered Items"]
    wi_df["Delta Staff Shifts"] = wi_df["New Staff Needed"] - wi_df["Original Staff Needed"]

    wi_df["Extra Revenue"] = wi_df["Delta Delivered Items"] * config.REVENUE_PER_ITEM_DELIVERED
    wi_df["Extra Cost"] = wi_df["Delta Staff Shifts"] * config.COST_PER_STAFF_SHIFT
    wi_df["Net Benefit"] = wi_df["Extra Revenue"] - wi_df["Extra Cost"]

    remaining_undelivered = sum(carry_over.values())

    summary = pd.DataFrame([
        ["Target DC", target_dc_name],
        ["Scenario", f"Capacity increased by {int((capacity_multiplier-1)*100)}%"],
        ["Extra Items Delivered in Horizon", f"{int(wi_df['Delta Delivered Items'].sum()):,}"],
        ["Extra Staff Shifts Required", f"{int(wi_df['Delta Staff Shifts'].sum()):,}"],
        ["Remaining Backlog at Horizon End", f"{int(remaining_undelivered):,} items"],
        ["Net Economic Benefit", f"{wi_df['Net Benefit'].sum():,.0f}"],
    ], columns=["Metric", "Value"])

    cost_benefit = pd.DataFrame([
        ["Extra Revenue", wi_df["Extra Revenue"].sum()],
        ["Extra Cost", wi_df["Extra Cost"].sum()],
        ["Net Benefit", wi_df["Net Benefit"].sum()],
    ], columns=["Metric", "Value"])

    return {"detail": wi_df, "summary": summary, "cost_benefit": cost_benefit}
