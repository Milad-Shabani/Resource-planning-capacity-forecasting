"""
Core forecasting engine.

This is a demand-ALLOCATION model, not a time-series model: it takes a
network-wide sales forecast as an external input and distributes it across
(DC x Time Window) slots using a "Dynamic Spatial Share" learned from
history, then applies two real-world operational constraints:

  1. Closed-Day Demand Rollforward — demand assigned to a slot that is
     closed that day (capacity = 0) is not discarded; it is carried forward
     and added to the next open day for that same DC/time-window.
  2. Capacity Capping — a slot can never deliver more than its physical
     capacity allows; anything above the cap is also carried forward.

See docs/methodology.md for the full write-up.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from . import config
from .date_utils import date_range, shift, weekday_name

Key = Tuple[str, str]  # (DC ID, Time Scope)


@dataclass
class ForecastInputs:
    historical: pd.DataFrame
    sales_forecast: pd.DataFrame
    order_cycle_time: pd.DataFrame


@dataclass
class ForecastArtifacts:
    """Everything the forecast step learns from history, kept around so the
    backtester and the what-if scenario module can reuse the exact same
    lookups instead of recomputing them."""
    roster: pd.DataFrame
    lag_lookup: Dict[str, int]
    capacity_lookup: Dict[Tuple[str, str, str], float]
    items_per_order_ts: Dict[Tuple[str, str], float]
    items_per_order_dc: Dict[str, float]
    items_per_order_global: float
    fallback_share: Dict[Tuple[str, str], float]
    weighted_share_lookup: Dict[Tuple[str, str, str], float]
    weighted_total_by_weekday: Dict[str, float]
    sale_lookup: Dict[str, float]


def _items_per_order(artifacts: ForecastArtifacts, dc: str, ts: str) -> float:
    """Order-to-item conversion, applied hierarchically: prefer the
    (DC, time-window) ratio, fall back to the DC-level ratio, then the
    network-wide ratio, so sparse slots still get a sensible conversion."""
    v = artifacts.items_per_order_ts.get((dc, ts), np.nan)
    if pd.notna(v) and v > 0:
        return v
    v = artifacts.items_per_order_dc.get(dc, np.nan)
    return v if (pd.notna(v) and v > 0) else artifacts.items_per_order_global


def _weekday_share(artifacts: ForecastArtifacts, dc: str, ts: str, weekday: str) -> float:
    """Recency-weighted share of network demand this (DC, time-window) slot
    captures on a given weekday. Falls back to the plain historical share of
    the slot (ignoring weekday) if there is no weekday-specific history."""
    own = artifacts.weighted_share_lookup.get((dc, ts, weekday))
    if own is not None:
        total = artifacts.weighted_total_by_weekday.get(weekday, 0)
        return own / total if total > 0 else 0
    return artifacts.fallback_share.get((dc, ts), 0)


def build_artifacts(inputs: ForecastInputs) -> ForecastArtifacts:
    hd = inputs.historical

    roster = hd[["DC ID", "DC Name", "Service Type", "State", "TS"]].drop_duplicates()

    dc_master = hd[["DC ID", "DC Name", "Service Type", "State"]].drop_duplicates()
    dc_master = dc_master.merge(
        inputs.order_cycle_time[["DC ID", "Order Cycle Time (Minutes)"]],
        on="DC ID", how="left",
    )
    dc_master["lag_days"] = (dc_master["Order Cycle Time (Minutes)"].fillna(0) / 1440).round().astype(int)
    lag_lookup = dc_master.set_index("DC ID")["lag_days"].to_dict()

    capacity_lookup = hd.set_index(["DC ID", "TS", "Weekday"])["Capacity"].to_dict()

    ts_agg = hd.groupby(["DC ID", "TS"])[["Items", "Orders"]].sum()
    items_per_order_ts = (ts_agg["Items"] / ts_agg["Orders"].replace(0, np.nan)).to_dict()

    dc_agg = hd.groupby("DC ID")[["Items", "Orders"]].sum()
    items_per_order_dc = (dc_agg["Items"] / dc_agg["Orders"].replace(0, np.nan)).to_dict()

    items_per_order_global = hd["Items"].sum() / hd["Orders"].sum()

    total_items_by_slot = hd.groupby(["DC ID", "TS"])["Items"].sum()
    fallback_share = (total_items_by_slot / hd["Items"].sum()).to_dict()

    # --- Dynamic Spatial Share, weighted toward recent history -----------
    hd = hd.copy()
    hd["DateOrd"] = pd.to_datetime(hd["DateNorm"]).map(lambda d: d.toordinal())
    max_ord = hd["DateOrd"].max()
    half_life = config.RECENCY_HALF_LIFE_DAYS
    hd["recency_weight"] = np.exp((hd["DateOrd"] - max_ord) / half_life)

    weighted_items = (
        hd.groupby(["DC ID", "TS", "Weekday"])
        .apply(lambda x: (x["Items"] * x["recency_weight"]).sum())
    )
    weighted_total_by_weekday = weighted_items.groupby(level=2).sum().to_dict()
    weighted_share_lookup = weighted_items.to_dict()

    sale_lookup = inputs.sales_forecast.set_index("Sale Date")["Sale Items Forecast"].to_dict()

    return ForecastArtifacts(
        roster=roster,
        lag_lookup=lag_lookup,
        capacity_lookup=capacity_lookup,
        items_per_order_ts=items_per_order_ts,
        items_per_order_dc=items_per_order_dc,
        items_per_order_global=items_per_order_global,
        fallback_share=fallback_share,
        weighted_share_lookup=weighted_share_lookup,
        weighted_total_by_weekday=weighted_total_by_weekday,
        sale_lookup=sale_lookup,
    )


def generate_forecast(
    artifacts: ForecastArtifacts,
    start_date: str = None,
    horizon_days: int = None,
) -> pd.DataFrame:
    """Run the end-to-end allocation loop over the forecast horizon.

    Returns a DataFrame at (Delivery Date x DC ID x Time Scope) grain with
    forecast items/orders delivered, staff needed, utilization and a risk
    classification — plus a breakdown of same-day vs. rolled-forward demand.
    """
    start_date = start_date or config.FORECAST_START_DATE
    horizon_days = horizon_days or config.FORECAST_HORIZON_DAYS
    forecast_dates = date_range(start_date, horizon_days)

    roster_list = list(artifacts.roster.itertuples(index=False, name=None))
    carry_over: Dict[Key, float] = {}
    rows = []

    for d in forecast_dates:
        wd = weekday_name(d)
        for dc, dc_name, service_type, state, ts in roster_list:
            lag = artifacts.lag_lookup.get(dc, 0)
            sale_date = shift(d, -lag)
            sale_forecast_items = artifacts.sale_lookup.get(sale_date, 0)

            cap = artifacts.capacity_lookup.get((dc, ts, wd), 0)
            key = (dc, ts)
            own_items = _weekday_share(artifacts, dc, ts, wd) * sale_forecast_items

            if cap > 0:
                deferred_in = carry_over.get(key, 0)
                requested_items = own_items + deferred_in

                ipo = _items_per_order(artifacts, dc, ts)
                max_items_today = cap * ipo
                delivered_items = min(requested_items, max_items_today)

                carry_over[key] = max(0, requested_items - delivered_items)
                fc_orders = delivered_items / ipo if ipo else 0
                staff_needed = np.ceil(fc_orders / config.ORDERS_PER_STAFF_PER_SHIFT)

                rows.append((d, dc, dc_name, ts, service_type, state, cap,
                             delivered_items, fc_orders, staff_needed,
                             own_items, deferred_in))
            else:
                # Closed slot: nothing is delivered, but demand is not lost —
                # it rolls forward to the next open day for this same slot.
                carry_over[key] = carry_over.get(key, 0) + own_items
                rows.append((d, dc, dc_name, ts, service_type, state, cap,
                             0.0, 0.0, 0.0, own_items, carry_over[key]))

    fc = pd.DataFrame(rows, columns=[
        "Delivery Date", "DC ID", "DC Name", "Time Scope", "Service Type", "State", "Capacity",
        "Forecast Delivered Items", "Forecast Delivered Orders", "Est. Staff Needed",
        "Of Which: Same-Day Demand", "Of Which: Deferred From Closed Day(s)",
    ])
    fc["Capacity Utilization"] = np.where(
        fc["Capacity"] > 0, fc["Forecast Delivered Orders"] / fc["Capacity"], np.nan
    )
    fc["Risk Category"] = [classify_risk(u, c) for u, c in zip(fc["Capacity Utilization"], fc["Capacity"])]

    int_cols = ["Forecast Delivered Items", "Forecast Delivered Orders", "Est. Staff Needed",
                "Of Which: Same-Day Demand", "Of Which: Deferred From Closed Day(s)"]
    fc[int_cols] = fc[int_cols].round().astype(int)
    fc = fc.sort_values(["Delivery Date", "DC ID", "Time Scope"]).reset_index(drop=True)

    undelivered_at_end = {k: v for k, v in carry_over.items() if v > 0.01}
    fc.attrs["undelivered_at_horizon_end"] = undelivered_at_end
    return fc


def classify_risk(utilization: float, capacity: float) -> str:
    t = config.RISK_THRESHOLDS
    if capacity <= 0:
        return "Closed (demand deferred to next open day)"
    if pd.isna(utilization):
        return "Closed"
    if utilization > t["overflow"]:
        return "Overflow"
    if utilization >= t["high_risk"]:
        return "High risk"
    if utilization >= t["healthy_low"]:
        return "Healthy"
    if utilization >= t["underutilized_low"]:
        return "Underutilized"
    return "Surplus"
