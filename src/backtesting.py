"""
Leave-one-day-out cross-validation.

For every historical day, we retrain the spatial share using all *other*
days, predict that held-out day, and compare against what actually happened.
We evaluate accuracy at two independent levels (see docs/methodology.md
section 4.2 for why this split matters):

  * Demand Accuracy     — raw model quality, before any capacity constraint.
  * Capacity Accuracy   — accuracy after applying capacity capping, i.e. the
                          number that reflects real operational performance.
"""
import numpy as np
import pandas as pd

from .forecasting import _items_per_order, ForecastArtifacts


def run_backtest(historical: pd.DataFrame, artifacts: ForecastArtifacts) -> pd.DataFrame:
    bt_parts = []

    for d in sorted(historical["DateNorm"].unique()):
        train = historical[historical["DateNorm"] != d]
        test = historical[historical["DateNorm"] == d]

        tr = train.groupby(["DC ID", "TS"])["Items"].sum().reset_index()
        tr["share"] = tr["Items"] / train["Items"].sum()

        pred = test[["DateNorm", "DC ID", "TS", "Weekday", "Items", "Orders"]].merge(
            tr[["DC ID", "TS", "share"]], on=["DC ID", "TS"], how="left"
        ).fillna(0)

        network_items = test["Items"].sum()
        pred["raw_pred_items"] = pred["share"] * network_items
        pred["ipo"] = pred.apply(lambda x: _items_per_order(artifacts, x["DC ID"], x["TS"]), axis=1)
        pred["pred_orders_raw"] = pred["raw_pred_items"] / pred["ipo"]

        pred["cap"] = pred.apply(
            lambda x: artifacts.capacity_lookup.get((x["DC ID"], x["TS"], x["Weekday"]), 0), axis=1
        )
        pred["capacity_items"] = pred["cap"] * pred["ipo"]
        pred["capped_pred_items"] = np.minimum(pred["raw_pred_items"], pred["capacity_items"])

        bt_parts.append(pred)

    bt = pd.concat(bt_parts)
    bt["pred_orders"] = bt["capped_pred_items"] / bt["ipo"]
    return bt


def _metrics(actual, pred, label) -> list:
    actual, pred = np.array(actual, dtype=float), np.array(pred, dtype=float)
    err = pred - actual
    abs_err = np.abs(err)
    mask = actual > 0

    return [
        label,
        round(abs_err.mean(), 2),
        round(np.sqrt((err ** 2).mean()), 2),
        round(err.mean(), 2),
        round((abs_err[mask] / actual[mask]).mean() * 100, 1),
        round(abs_err.sum() / actual.sum() * 100, 1),
        round(np.percentile(abs_err, 90), 2),
        round((err < 0).mean() * 100, 1),
        round((err > 0).mean() * 100, 1),
        round(((abs_err / np.clip(actual, 1, None)) <= 0.2).mean() * 100, 1),
        len(actual),
    ]


def summarize_backtest(bt: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            _metrics(bt["Items"], bt["raw_pred_items"], "Demand Items (raw)"),
            _metrics(bt["Items"], bt["capped_pred_items"], "Capacity Items (constrained)"),
            _metrics(bt["Orders"], bt["pred_orders_raw"], "Demand Orders (raw)"),
            _metrics(bt["Orders"], bt["pred_orders"], "Capacity Orders (constrained)"),
        ],
        columns=["Segment", "MAE", "RMSE", "Bias", "MAPE %", "WAPE %",
                 "P90 AE", "Under Forecast %", "Over Forecast %", "Hit Rate ±20%", "n"],
    )
