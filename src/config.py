"""
Central configuration for the DC Capacity Forecasting pipeline.
Edit these values to point at a different dataset or forecast horizon.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "sample"
OUTPUT_DIR = ROOT_DIR / "outputs"

HISTORICAL_DELIVERY_FILE = DATA_DIR / "historical_delivery_data.csv"
SALES_FORECAST_FILE = DATA_DIR / "sales_forecast.csv"
ORDER_CYCLE_TIME_FILE = DATA_DIR / "order_cycle_time.csv"

OUTPUT_WORKBOOK = OUTPUT_DIR / "DC_Capacity_Forecast.xlsx"

# ---------------------------------------------------------------------------
# Forecast horizon
# ---------------------------------------------------------------------------
FORECAST_START_DATE = "2026-07-01"   # first day of the forecast horizon
FORECAST_HORIZON_DAYS = 30           # length of the forecast horizon

# ---------------------------------------------------------------------------
# Business assumptions
# ---------------------------------------------------------------------------
ORDERS_PER_STAFF_PER_SHIFT = 40      # avg. orders one staff member can process in a shift

# Capacity utilization thresholds used to classify each DC / time-window / day
RISK_THRESHOLDS = {
    "overflow": 1.00,       # utilization > 100%          -> Overflow (SLA breach risk)
    "high_risk": 0.85,      # 85% <= utilization <= 100%  -> High risk
    "healthy_low": 0.50,    # 50% <= utilization < 85%    -> Healthy
    "underutilized_low": 0.20,  # 20% <= utilization < 50% -> Underutilized
    # utilization < 20%                                    -> Surplus
}

AT_RISK_DAY_SHARE_THRESHOLD = 0.30    # DC flagged "at risk" if >=30% of days are High risk/Overflow
SURPLUS_DAY_SHARE_THRESHOLD = 0.70    # DC flagged "surplus" if >=70% of days are in Surplus band

# ---------------------------------------------------------------------------
# Recency weighting for the Dynamic Spatial Share allocation
# ---------------------------------------------------------------------------
RECENCY_HALF_LIFE_DAYS = 7   # exponential decay constant (in days) for weighting history

# ---------------------------------------------------------------------------
# What-if scenario analysis (cost/benefit)
# ---------------------------------------------------------------------------
COST_PER_STAFF_SHIFT = 20         # currency units per staff shift
REVENUE_PER_ITEM_DELIVERED = 1.5  # currency units of margin per item successfully delivered
