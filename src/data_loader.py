"""
Load and standardize the three raw inputs the model needs:
  1. Historical Delivery Data  — DC-level actuals (capacity, items, orders)
  2. Sales Forecast            — network-wide top-line demand forecast
  3. Order Cycle Time          — sale-to-delivery lag per DC
"""
import pandas as pd
from . import config
from .date_utils import fmt, to_date


def load_historical_delivery_data(path=None) -> pd.DataFrame:
    path = path or config.HISTORICAL_DELIVERY_FILE
    df = pd.read_csv(path)
    df = df.rename(columns={
        "Items Delivered": "Items",
        "Orders Delivered": "Orders",
        "DC Capacity": "Capacity",
        "Time Scope": "TS",
        "Delivery Date": "Date",
    })
    df["DateNorm"] = df["Date"].apply(lambda x: fmt(to_date(x)))
    return df


def load_sales_forecast(path=None) -> pd.DataFrame:
    path = path or config.SALES_FORECAST_FILE
    df = pd.read_csv(path)
    df["Sale Date"] = df["Sale Date"].apply(lambda x: fmt(to_date(x)))
    return df


def load_order_cycle_time(path=None) -> pd.DataFrame:
    path = path or config.ORDER_CYCLE_TIME_FILE
    return pd.read_csv(path)


def load_all():
    return (
        load_historical_delivery_data(),
        load_sales_forecast(),
        load_order_cycle_time(),
    )
