# Methodology

## 1. Data analysis approach

The model is a **demand-allocation model**, not a time-series model. Rather
than forecasting sales directly, it takes an existing network-wide sales
forecast as an input and distributes ("allocates") that demand across
Distribution Centers (DCs) and delivery time windows.

To stay responsive to recent shifts in network behavior, the allocation uses
a **Dynamic Spatial Share**: each slot's share of network demand is computed
from historical patterns with more weight placed on more recent
observations (**recency weighting**), so recent changes in customer behavior
or network structure are reflected faster than a simple historical average
would allow.

## 2. How the source data is used

| Source | Used for |
|---|---|
| **Historical Delivery Data** | Extracting each slot's share of network demand by weekday, and computing the items-per-order conversion rate. |
| **Order Cycle Time** | Converting a *delivery date* into the *sale date* that generated it (`sale date = delivery date - lag`). |
| **Sales Forecast** | The primary top-line demand input driving the whole allocation. |

## 3. Forecasting logic

The end-to-end pipeline (`src/forecasting.py`) runs as follows for every
`(Delivery Date, DC, Time Scope)` combination in the forecast horizon:

1. **Inputs** — historical delivery data, the sales forecast, and order cycle
   time are loaded and standardized.
2. **Feature extraction** — weekday, capacity, and slot-level identifiers are
   derived/cleaned from the raw data.
3. **Weekday pattern learning** — historical demand patterns are learned per
   weekday to capture time-of-week seasonality.
4. **Items-per-order estimation** — the item-to-order conversion ratio is
   computed hierarchically (slot → DC → network) so sparse slots still get a
   sensible ratio.
5. **Order cycle time mapping** — for every forecast delivery date, the
   corresponding sale date is derived using the DC's lag.
6. **Demand extraction** — the network-wide forecast demand for that sale
   date is pulled from the Sales Forecast input.
7. **Dynamic Spatial Share allocation** — that demand is split across slots
   using the recency-weighted historical share.
8. **Closed-day demand rollforward** — if a slot is closed that day (capacity
   = 0), its demand is not discarded — it carries forward to the next open
   day for that same slot (see §4 below).
9. **Capacity capping** — a slot's final demand is compared to its physical
   capacity; anything above the cap is deferred to the next day, exactly like
   a closed day.
10. **Forecast generation** — the final output (delivered items, delivered
    orders, staffing need, utilization, risk category) is produced.
11. **Backtesting & validation** — model performance is evaluated with MAE,
    RMSE, Bias, MAPE and WAPE (see §5-6).
12. **Capacity analysis & what-if scenarios** — network-wide capacity
    analysis is run, plus scenario simulations for capacity changes.
13. **Management recommendations** — final, decision-ready recommendations
    for resource allocation and risk mitigation.

## 4. Closed-day demand rollforward (extra challenge)

Some DCs (in this synthetic dataset, the "Satellite Depot" type) close on a
specific weekday. If closures were treated as "zero demand," a large amount
of real network demand would simply vanish from the plan. Instead:

1. If a slot's capacity is zero on a given date, the model does **not**
   assume zero demand for that slot.
2. It estimates the demand that *would have* occurred using a
   weekday-independent **base share** of network demand for that slot.
3. This demand is carried forward to the **next open day** for the same DC
   and time window.
4. If several consecutive days are closed, the demand cascades forward and
   accumulates until it reaches the first open day.

This is what produces the periodic utilization spikes visible in
`docs/images/network_utilization.png` — every closure is immediately
followed by a demand shock on the next open day.

## 5. Key assumptions

- **Order Cycle Time** represents the lag (in minutes, rounded to whole days)
  between a sale and its arrival at a DC, and is the basis for mapping a
  delivery date back to the sale date that generated it.
- **Items-per-order conversion** is estimated from history and applied
  hierarchically across three levels (slot → DC → network) since the sales
  forecast is provided in items but capacity is expressed in orders.
- **Staffing**: each staff member can process ~40 orders per shift (see
  `config.ORDERS_PER_STAFF_PER_SHIFT`); this drives the staffing requirement.
- **DC Capacity** is treated as the hard operational ceiling for a slot.
  Historical observations that exceed the recorded capacity are treated as
  operational exceptions (overtime, temporary capacity increases, or data
  noise) rather than evidence that the true ceiling is higher.
- **Service Type** does not directly influence the core allocation logic; it
  is used only in the risk/segmentation analysis.

## 6. Model limitations

**Data limitations**
- Some concepts (the exact operational meaning of "capacity", the role of
  service type) are not formally documented in the source data and are
  covered by modeling assumptions instead.
- Data-quality inconsistencies (e.g. mismatched weekday/date pairs, outliers)
  can affect output accuracy if present in a real deployment.

**Modeling limitations**
- The model does not directly model long-term demand trends. Dynamic Share
  captures *recent* shifts, but long-term seasonality, structural changes,
  and non-linear effects are not modeled explicitly.
- The model focuses on capacity allocation and planning; it treats the sales
  forecast as an external input, so its output quality is partly bounded by
  the quality of that upstream forecast.

**Operational limitations**
- Public holidays, staff leave, ad-hoc shift changes, and last-minute
  operational decisions are not modeled.
- External factors (marketing campaigns, weather, one-off shifts in customer
  behavior) are not incorporated.

## 7. Backtesting methodology

**Leave-one-day-out cross-validation**: for every historical day, the model
is retrained on all *other* days, then used to predict the held-out day,
which is compared against the actual observed values. This is repeated for
every day in the historical window.

### Separating demand accuracy from operational accuracy

In many capacity models, applying operational constraints directly can mask
real forecasting error. For example: if actual demand is 1,000 units,
capacity is 500 units, and the raw model forecast is 1,500 units, the
operational output after capping is limited to 500 units — identical to
actual delivered volume. Comparing only the final, capped output against
actuals would hide the fact that the raw forecast was off by 500 units.

To avoid this, backtesting is evaluated at **two independent levels**:

- **Demand Accuracy** — raw model quality *before* any capacity constraint;
  measures the model's ability to estimate true demand correctly.
- **Capacity Accuracy** — accuracy *after* operational constraints are
  applied; measures real-world operational performance.

This separation isolates forecasting-model error from error caused by the
network's physical constraints.

### Accuracy metrics

| Metric | Interpretation |
|---|---|
| **MAE** | Average absolute error — the typical size of a miss. |
| **RMSE** | Penalizes large errors more heavily; flags outlier predictions. |
| **Bias** | Average signed error — systematic over/under-forecasting. |
| **MAPE** | Average relative error, as a percentage. |
| **WAPE** | Absolute error weighted by total volume — the standard metric for high-volume logistics data, since it isn't distorted by low-volume slots. |
| **P90 AE** | The error threshold under which 90% of observations fall — describes tail behavior. |
| **Under/Over Forecast %** | Share of slots where the model under/over-predicted. |
| **Hit Rate (±20%)** | Share of forecasts within ±20% of the actual value. |

**WAPE is the primary network performance metric** because it is sensitive
to operational volume and gives a more realistic picture of network-wide
performance than an unweighted average of percentage errors.

## 8. Future development ideas

- **Native sales forecasting**: replace the externally-provided sales
  forecast with an in-house time-series model (e.g. Prophet, ARIMA, or a
  gradient-boosted model) to remove the dependency on an external input.
  This project deliberately uses a business-logic-driven allocation approach
  instead, given the limited historical window available and the risk of
  overfitting a more complex model to it.
- **Multi-scenario optimization**: jointly evaluate multiple capacity,
  shift, and resource-allocation scenarios to find the best combined
  operational decision, instead of one scenario at a time.
- **Advanced cost/benefit modeling**: build out a fuller economic module
  that accounts for overtime cost, staff-transfer cost, and budget
  constraints.
- **External factor integration**: incorporate weather, marketing campaigns,
  and calendar events (holidays, sale events) to improve forecast accuracy.
- **BI dashboard deployment**: publish an interactive dashboard (e.g. Power
  BI, Looker, or a lightweight web app) for real-time capacity and scenario
  analysis.
