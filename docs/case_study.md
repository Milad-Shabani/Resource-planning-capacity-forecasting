# Case Study Brief: NovaCart Fulfillment Network Capacity Forecasting

> This is the assignment brief this project is built around — written the way a
> real operations-planning take-home task might read. `NovaCart` is a fictional
> online retail company created for this portfolio piece; all data in this
> repository is synthetically generated (see `scripts/generate_sample_data.py`).

## Background

NovaCart is a fast-growing online retail company. Customer orders are fulfilled
through a network of **Distribution Centers (DCs)**, each operating multiple
daily **delivery time windows** (e.g. Morning / Afternoon / Evening). Each
(DC, time window) "slot" has a limited daily processing **capacity**.

Every month, the Commercial team produces a single, network-wide **sales
forecast** (total items expected to sell, per day). The Operations Planning
team's job is to turn that one top-line number into an actionable,
slot-by-slot delivery plan — and to flag where the network will run out of
capacity before it happens.

## Objective

Using the data provided, design a model that converts the network-wide sales
forecast into a **delivery volume forecast** for the upcoming month, broken
down by **DC** and **delivery time window**, and evaluate the impact on the
network's operational capacity.

You are free to use any tools you consider appropriate (Excel, Python, SQL,
BI tools, or a mix). This exercise evaluates your ability to analyze data,
design planning logic, forecast, validate a model, and produce
data-driven operational recommendations — not mastery of a specific tool.

> *We don't expect a perfect or complete solution. How you think, the
> assumptions you make, the quality of your reasoning, and the soundness of
> your decisions matter more than the sophistication of the model.*

## Available Data

**1. Historical Delivery Data** — DC-level operational history:
`DC ID`, `DC Name`, `Delivery Date`, `Weekday`, `Time Scope`, `DC Capacity`,
`Orders Delivered`, `Items Delivered`, `Service Type`, `State`.

**2. Sales Forecast** — network-wide top-line demand forecast:
`Sale Date`, `Sale Items Forecast`.

**3. Order Cycle Time** — the lag between a sale and the order arriving at a DC:
`DC ID`, `DC Name`, `Order Cycle Time (Minutes)`.

## Expected Deliverables

**1. Forecast Output** — at minimum, at the grain of
`Delivery Date x DC ID x Time Scope`:

| Delivery Date | DC ID | DC Name | Time Scope | Forecast Delivered Items | Forecast Delivered Orders | Capacity Utilization |
|---|---|---|---|---|---|---|

**2. Methodology** — full documentation of the data analysis approach,
assumptions, forecasting logic, how the source data was used, model
limitations, and ideas for future development.

**3. Validation & Backtesting** — the proposed approach must be validated
against historical data, at minimum including a forecast-vs-actual
comparison, accuracy metrics, and an error analysis.

**4. Capacity Analysis** — based on the generated forecast:
- Calculate capacity utilization for every DC.
- Identify DCs at risk of a capacity shortfall.
- Identify DCs with surplus capacity.
- Analyze the impact of the forecast on the operational network.

**5. Management Summary** — one page, maximum:
- Key findings
- Main risks
- Key recommendations
- Suggested actions for managing network capacity

## Extra Challenge (Optional)

Some DCs may have calendar restrictions or non-standard working days.
If you're up for it, explain how you would incorporate DC-specific working
calendars into the forecasting and capacity-planning model, and what impact
that would have on the results.

---

**How this repository answers the brief** is documented in
[`methodology.md`](methodology.md) and demonstrated end-to-end by running
`python -m src.main` (see the root [`README.md`](../README.md) for
instructions).
