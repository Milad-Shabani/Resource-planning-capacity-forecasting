# `data/raw/`

Drop your own real data here if you want to run this pipeline against a real
fulfillment network instead of the bundled synthetic dataset.

Expected files and columns (see `data/sample/` for a working example, and
[`docs/methodology.md`](../../docs/methodology.md) for how each field is
used):

**`historical_delivery_data.csv`**
`DC ID, DC Name, Delivery Date, Weekday, Time Scope, DC Capacity, Orders Delivered, Items Delivered, Service Type, State`

**`sales_forecast.csv`**
`Sale Date, Sale Items Forecast`

**`order_cycle_time.csv`**
`DC ID, DC Name, Order Cycle Time (Minutes)`

Then update the paths in `src/config.py` (`DATA_DIR` or the individual file
constants) to point here instead of `data/sample/`.
