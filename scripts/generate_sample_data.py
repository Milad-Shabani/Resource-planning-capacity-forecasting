"""
Generate synthetic sample data for the NovaCart DC Capacity Forecasting project.

This script creates a fully synthetic dataset that mimics the structure and
statistical patterns of a real last-mile fulfillment network (weekday
seasonality, DC-level capacity limits, closed days, item/order ratios, an
order-to-delivery lag, etc.) WITHOUT using any real company data.

Run:
    python scripts/generate_sample_data.py

Outputs (written to data/sample/):
    historical_delivery_data.csv
    sales_forecast.csv
    order_cycle_time.csv
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)

# --------------------------------------------------------------------------
# 1. Network roster: Distribution Centers (DCs) x Delivery Time Windows
# --------------------------------------------------------------------------
REGIONS = ["North", "South", "East", "West", "Central"]
TIME_SCOPES = ["Morning", "Afternoon", "Evening"]
N_DCS = 24

dc_ids = [f"DC_{i:03d}" for i in range(1, N_DCS + 1)]
dc_region = {dc: REGIONS[i % len(REGIONS)] for i, dc in enumerate(dc_ids)}
dc_type = {dc: ("Urban Hub" if i % 3 == 0 else "Regional Center" if i % 3 == 1 else "Satellite Depot")
           for i, dc in enumerate(dc_ids)}

# Each DC has a "base weight" (relative share of network demand) and a
# baseline capacity per time-window. A handful of DCs are deliberately
# undersized relative to their demand share (bottlenecks) and a handful are
# oversized (surplus capacity) so the forecasting model has something
# interesting to discover.
base_weight = rng.lognormal(mean=0.0, sigma=0.65, size=N_DCS)
base_weight = base_weight / base_weight.sum()
dc_weight = dict(zip(dc_ids, base_weight))

bottleneck_dcs = {dc_ids[2], dc_ids[9]}          # chronically undersized
surplus_dcs = {dc_ids[5], dc_ids[14], dc_ids[20], dc_ids[7]}  # chronically oversized

# Some DCs are "Satellite Depots" that close on Sundays (capacity = 0 that
# day) -> this is what drives the closed-day demand rollforward logic.
closed_weekday_by_dc = {
    dc: (6 if dc_type[dc] == "Satellite Depot" else None)  # 6 = Sunday
    for dc in dc_ids
}

# --------------------------------------------------------------------------
# 2. Order cycle time (minutes between a sale and it arriving at a DC)
# --------------------------------------------------------------------------
order_cycle_time = pd.DataFrame({
    "DC ID": dc_ids,
    "DC Name": [f"{dc_region[dc]} {dc_type[dc]} {dc}" for dc in dc_ids],
    "Order Cycle Time (Minutes)": rng.choice([0, 720, 1440, 2880], size=N_DCS,
                                              p=[0.25, 0.35, 0.3, 0.1]),
})
order_cycle_time.to_csv("data/sample/order_cycle_time.csv", index=False)

# --------------------------------------------------------------------------
# 3. Company-wide sales forecast (items expected to sell, per calendar day)
# --------------------------------------------------------------------------
HIST_START = date(2026, 4, 1)
HIST_DAYS = 91                       # 91 days of "actuals" for training/backtesting
FCST_DAYS = 30                       # 30-day forecast horizon (the "next month")

all_dates = [HIST_START + timedelta(days=i) for i in range(HIST_DAYS + FCST_DAYS + 10)]

def weekday_seasonality(d):
    # Sales are higher midweek and on weekends, lower on Mondays
    factor = {0: 0.85, 1: 0.95, 2: 1.0, 3: 1.05, 4: 1.15, 5: 1.25, 6: 1.1}
    return factor[d.weekday()]

sales_rows = []
base_daily_items = 55000
trend_growth_per_day = 0.0022  # ~2.2%/week compounding growth
for i, d in enumerate(all_dates):
    trend = (1 + trend_growth_per_day) ** i
    seasonal = weekday_seasonality(d)
    noise = rng.normal(1.0, 0.05)
    items = max(0, base_daily_items * trend * seasonal * noise)
    sales_rows.append((d.strftime("%Y-%m-%d"), round(items)))

sales_forecast = pd.DataFrame(sales_rows, columns=["Sale Date", "Sale Items Forecast"])
sales_forecast.to_csv("data/sample/sales_forecast.csv", index=False)
sale_lookup = dict(zip(sales_forecast["Sale Date"], sales_forecast["Sale Items Forecast"]))

# --------------------------------------------------------------------------
# 4. Historical delivery data (actuals) — used for training + backtesting
# --------------------------------------------------------------------------
lag_days_by_dc = {row["DC ID"]: int(round(row["Order Cycle Time (Minutes)"] / 1440))
                   for _, row in order_cycle_time.iterrows()}

ts_weight = {"Morning": 0.30, "Afternoon": 0.45, "Evening": 0.25}

hist_rows = []
for i in range(HIST_DAYS):
    d = all_dates[i]
    weekday_name = d.strftime("%A")
    for dc in dc_ids:
        lag = lag_days_by_dc[dc]
        sale_date = (d - timedelta(days=lag)).strftime("%Y-%m-%d")
        network_items = sale_lookup.get(sale_date, base_daily_items)

        closed_wd = closed_weekday_by_dc[dc]
        for ts in TIME_SCOPES:
            share = dc_weight[dc] * ts_weight[ts]
            demand_items = network_items * share * rng.normal(1.0, 0.08)
            demand_items = max(0, demand_items)

            if closed_wd is not None and d.weekday() == closed_wd:
                capacity = 0
                delivered_items = 0
            else:
                # capacity sized around ~112% of "typical" demand, except
                # deliberately undersized/oversized DCs
                typical_ratio = 1.65
                if dc in bottleneck_dcs:
                    typical_ratio = 0.75
                elif dc in surplus_dcs:
                    typical_ratio = 8.0
                items_per_order_local = rng.normal(3.1, 0.3)
                capacity_orders = max(5, round((demand_items / items_per_order_local) * typical_ratio))
                capacity = capacity_orders
                delivered_items = min(demand_items, capacity * items_per_order_local)

            items_per_order_local = rng.normal(3.1, 0.25)
            delivered_orders = delivered_items / items_per_order_local if delivered_items > 0 else 0

            hist_rows.append((
                dc, f"{dc_region[dc]} {dc_type[dc]} {dc}", d.strftime("%Y-%m-%d"),
                weekday_name, ts, capacity,
                round(delivered_orders), round(delivered_items),
                dc_type[dc], dc_region[dc]
            ))

historical = pd.DataFrame(hist_rows, columns=[
    "DC ID", "DC Name", "Delivery Date", "Weekday", "Time Scope", "DC Capacity",
    "Orders Delivered", "Items Delivered", "Service Type", "State"
])
historical.to_csv("data/sample/historical_delivery_data.csv", index=False)

print("Sample data generated in data/sample/:")
print(f"  - historical_delivery_data.csv  ({len(historical):,} rows, {N_DCS} DCs x {len(TIME_SCOPES)} windows x {HIST_DAYS} days)")
print(f"  - sales_forecast.csv            ({len(sales_forecast):,} rows)")
print(f"  - order_cycle_time.csv          ({len(order_cycle_time):,} rows)")
print(f"\nForecast horizon starts on: {all_dates[HIST_DAYS].strftime('%Y-%m-%d')}")
print(f"Forecast horizon ends on:   {all_dates[HIST_DAYS + FCST_DAYS - 1].strftime('%Y-%m-%d')}")
