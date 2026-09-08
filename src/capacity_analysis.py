"""
Turn the raw forecast into decision-ready capacity analysis:
  - Daily utilization per DC and network-wide
  - At-risk DCs (structurally short on capacity)
  - Surplus DCs (structurally under-utilized — rebalancing candidates)
  - Risk breakdown by DC/service type
"""
import pandas as pd

from . import config
from .date_utils import weekday_name
from .forecasting import classify_risk


def daily_dc_summary(fc: pd.DataFrame) -> pd.DataFrame:
    dc_day = fc.groupby(["DC ID", "DC Name", "Service Type", "State", "Delivery Date"]).agg(
        Capacity=("Capacity", "sum"),
        Forecast_Orders=("Forecast Delivered Orders", "sum"),
        Staff_Needed=("Est. Staff Needed", "sum"),
    ).reset_index()
    dc_day["Utilization"] = dc_day["Forecast_Orders"] / dc_day["Capacity"].where(dc_day["Capacity"] > 0)
    dc_day["Risk Category"] = [classify_risk(u, c) for u, c in zip(dc_day["Utilization"], dc_day["Capacity"])]
    return dc_day


def monthly_dc_summary(dc_day: pd.DataFrame) -> pd.DataFrame:
    active = dc_day[dc_day["Capacity"] > 0]
    summary = active.groupby(["DC ID", "DC Name", "Service Type", "State"]).agg(
        active_days=("Delivery Date", "count"),
        avg_utilization=("Utilization", "mean"),
        max_utilization=("Utilization", "max"),
        total_capacity=("Capacity", "sum"),
        total_forecast_orders=("Forecast_Orders", "sum"),
        total_staff_needed=("Staff_Needed", "sum"),
        days_high_risk=("Risk Category", lambda s: s.isin(["High risk", "Overflow"]).sum()),
        days_overflow=("Risk Category", lambda s: (s == "Overflow").sum()),
        days_surplus=("Risk Category", lambda s: (s == "Surplus").sum()),
    ).reset_index()

    summary["month_utilization"] = summary["total_forecast_orders"] / summary["total_capacity"]
    summary["pct_days_high_risk"] = summary["days_high_risk"] / summary["active_days"]
    summary["pct_days_surplus"] = summary["days_surplus"] / summary["active_days"]
    return summary


def network_daily_summary(dc_day: pd.DataFrame) -> pd.DataFrame:
    net = dc_day.groupby("Delivery Date").agg(
        Capacity=("Capacity", "sum"),
        Forecast_Orders=("Forecast_Orders", "sum"),
        Total_Staff=("Staff_Needed", "sum"),
    ).reset_index()
    net["Weekday"] = net["Delivery Date"].apply(weekday_name)
    net["Utilization"] = net["Forecast_Orders"] / net["Capacity"].where(net["Capacity"] > 0)
    net = net.sort_values("Delivery Date")
    return net


def at_risk_dcs(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly[monthly["pct_days_high_risk"] >= config.AT_RISK_DAY_SHARE_THRESHOLD] \
        .sort_values("pct_days_high_risk", ascending=False)


def surplus_dcs(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly[monthly["pct_days_surplus"] >= config.SURPLUS_DAY_SHARE_THRESHOLD] \
        .sort_values("month_utilization")


def risk_by_service_type(monthly: pd.DataFrame) -> pd.DataFrame:
    type_summary = monthly.groupby("Service Type").agg(
        DC_Count=("DC ID", "count"),
        Avg_Utilization=("avg_utilization", "mean"),
        DCs_At_Risk=("pct_days_high_risk", lambda s: (s >= config.AT_RISK_DAY_SHARE_THRESHOLD).sum()),
        DCs_Surplus=("pct_days_surplus", lambda s: (s >= config.SURPLUS_DAY_SHARE_THRESHOLD).sum()),
    ).reset_index()
    type_summary["pct_at_risk"] = type_summary["DCs_At_Risk"] / type_summary["DC_Count"]
    type_summary["pct_surplus"] = type_summary["DCs_Surplus"] / type_summary["DC_Count"]
    return type_summary


def undelivered_at_horizon_end(fc: pd.DataFrame) -> pd.DataFrame:
    undelivered = fc.attrs.get("undelivered_at_horizon_end", {})
    roster = fc[["DC ID", "DC Name", "Service Type", "State", "Time Scope"]].drop_duplicates()
    rows = []
    for (dc, ts), amt in undelivered.items():
        info = roster[(roster["DC ID"] == dc) & (roster["Time Scope"] == ts)]
        if info.empty:
            continue
        info = info.iloc[0]
        rows.append((dc, info["DC Name"], info["Service Type"], info["State"], ts, int(round(amt))))
    return pd.DataFrame(rows, columns=[
        "DC ID", "DC Name", "Service Type", "State", "Time Scope", "Undelivered Items at Horizon End"
    ]).sort_values("Undelivered Items at Horizon End", ascending=False)
