"""
End-to-end pipeline:
  load data -> build forecast -> backtest -> capacity analysis ->
  what-if scenario -> export Excel workbook

Run from the project root:
    python -m src.main
"""
from . import config
from .data_loader import load_all
from .forecasting import ForecastInputs, build_artifacts, generate_forecast
from .backtesting import run_backtest, summarize_backtest
from .capacity_analysis import (
    daily_dc_summary, monthly_dc_summary, network_daily_summary,
    at_risk_dcs, surplus_dcs, risk_by_service_type, undelivered_at_horizon_end,
)
from .scenario_analysis import run_capacity_expansion_scenario
from .report_export import build_workbook, TITLE_FONT, SECTION_FONT, BODY_FONT, ITALIC_FONT


def main():
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("1/6  Loading data...")
    historical, sales_forecast, order_cycle_time = load_all()
    inputs = ForecastInputs(historical, sales_forecast, order_cycle_time)

    print("2/6  Building forecast artifacts (dynamic spatial share)...")
    artifacts = build_artifacts(inputs)

    print("3/6  Generating forecast over the horizon...")
    fc = generate_forecast(artifacts)

    print("4/6  Running leave-one-day-out backtest...")
    bt = run_backtest(historical, artifacts)
    bt_summary = summarize_backtest(bt)
    print(bt_summary.to_string(index=False))

    print("5/6  Running capacity analysis + what-if scenario...")
    dc_day = daily_dc_summary(fc)
    dc_monthly = monthly_dc_summary(dc_day)
    net_day = network_daily_summary(dc_day)
    risk_dcs = at_risk_dcs(dc_monthly)
    surplus = surplus_dcs(dc_monthly)
    type_summary = risk_by_service_type(dc_monthly)
    undeliv = undelivered_at_horizon_end(fc)

    # Pick the worst bottleneck DC (highest share of high-risk days) as the
    # subject of the what-if scenario.
    if len(risk_dcs):
        target_dc_name = risk_dcs.iloc[0]["DC Name"]
    else:
        target_dc_name = dc_monthly.sort_values("avg_utilization", ascending=False).iloc[0]["DC Name"]
    scenario = run_capacity_expansion_scenario(artifacts, target_dc_name, capacity_multiplier=1.5)

    net_util = fc["Forecast Delivered Orders"].sum() / fc["Capacity"].where(fc["Capacity"] > 0).sum() * 100
    total_demand = sum(
        sales_forecast.loc[sales_forecast["Sale Date"] == d, "Sale Items Forecast"].sum()
        for d in fc["Delivery Date"].unique()
    )

    methodology_lines = [
        ("DC CAPACITY FORECASTING — METHODOLOGY", TITLE_FONT),
        ("", BODY_FONT),
        ("1. Data analysis approach", SECTION_FONT),
        ("This is a demand-allocation model, not a time-series model. It takes an external "
         "network-wide sales forecast and distributes it across (DC x Time Window) slots using a "
         "Dynamic Spatial Share learned from history, with more weight given to recent days.", BODY_FONT),
        ("", BODY_FONT),
        ("2. Key assumptions", SECTION_FONT),
        ("- Order Cycle Time represents the lag between a sale and its arrival at a DC, and is used "
         "to map each delivery date back to the sale date that generated it.", BODY_FONT),
        (f"- Each staff member can process ~{config.ORDERS_PER_STAFF_PER_SHIFT} orders per shift; this "
         "ratio drives the staffing requirement.", BODY_FONT),
        ("- DC Capacity is treated as the hard operational ceiling for a given DC/time-window/weekday.", BODY_FONT),
        ("", BODY_FONT),
        ("3. Forecasting logic", SECTION_FONT),
        ("1. Map each delivery date to its corresponding sale date (shift by -lag days).", BODY_FONT),
        ("2. Pull the network-wide sales forecast for that sale date.", BODY_FONT),
        ("3. Multiply by the slot's dynamic, recency-weighted weekday share.", BODY_FONT),
        ("4. Add any demand rolled forward from a previous closed/over-capacity day.", BODY_FONT),
        ("5. Cap at the slot's capacity; anything above the cap rolls forward to the next day.", BODY_FONT),
        ("", BODY_FONT),
        ("4. Closed-day demand rollforward (extra challenge)", SECTION_FONT),
        ("If a slot is closed (capacity = 0) on a given day, demand is not discarded: it is estimated "
         "using the slot's weekday-independent base share and carried forward — cascading across "
         "multiple consecutive closed days if needed — to the next open day.", BODY_FONT),
        ("", BODY_FONT),
        ("5. Backtesting methodology", SECTION_FONT),
        ("Leave-one-day-out cross-validation. Predictions are capped at each slot's capacity before "
         "comparison, so the reported accuracy reflects real operational performance rather than raw, "
         "unconstrained demand error.", BODY_FONT),
    ]

    management_summary_lines = [
        ("DC CAPACITY FORECAST — MANAGEMENT SUMMARY", TITLE_FONT),
        (f"Forecast Period: {fc['Delivery Date'].min()} to {fc['Delivery Date'].max()}", SECTION_FONT),
        ("", BODY_FONT),
        ("KEY FINDINGS", SECTION_FONT),
        (f"- Total DCs analyzed: {fc['DC ID'].nunique()}", BODY_FONT),
        (f"- Total forecasted demand: {total_demand:,.0f} items", BODY_FONT),
        (f"- Total forecast deliveries: {fc['Forecast Delivered Items'].sum():,.0f} items", BODY_FONT),
        (f"- Network utilization: {net_util:.1f}%", BODY_FONT),
        (f"- Estimated total staff shifts needed: {fc['Est. Staff Needed'].sum():,}", BODY_FONT),
        (f"- DCs at structural risk: {len(risk_dcs)} | Surplus DCs: {len(surplus)}", BODY_FONT),
        ("", BODY_FONT),
        ("MAIN RISKS", SECTION_FONT),
        (f"- Bottlenecks: {target_dc_name} and similar DCs approach 100% capacity on most days.", BODY_FONT),
        ("- Demand clustering: rolled-forward demand from closed days creates sharp spikes on the next open day.", BODY_FONT),
        ("", BODY_FONT),
        ("KEY RECOMMENDATIONS", SECTION_FONT),
        ("1. Resource rebalancing: reallocate staff from surplus DCs to at-risk DCs using the 'Est. Staff Needed' column.", BODY_FONT),
        ("2. Review operating hours: extending time windows at high-risk DCs can absorb deferred demand.", BODY_FONT),
        ("3. Policy review: evaluate the cost/benefit of keeping chronically-deferred DCs open on their closed day.", BODY_FONT),
        (f"- Scenario simulation: increasing {target_dc_name}'s capacity by 50% yields a net economic benefit of "
         f"{scenario['cost_benefit'].iloc[2, 1]:,.0f} over the forecast horizon.", BODY_FONT),
    ]

    print("6/6  Exporting Excel workbook...")
    out_path = build_workbook(
        forecast_output=fc, network_daily=net_day, dc_monthly=dc_monthly,
        at_risk=risk_dcs, surplus=surplus, risk_by_type=type_summary,
        backtest_summary=bt_summary, undelivered=undeliv, scenario=scenario,
        methodology_lines=methodology_lines, management_summary_lines=management_summary_lines,
        output_path=config.OUTPUT_WORKBOOK,
    )
    print(f"\nSaved workbook to: {out_path}")
    print(f"Network utilization: {net_util:.1f}% | Staff needed: {fc['Est. Staff Needed'].sum():,} | "
          f"At-risk DCs: {len(risk_dcs)} | Surplus DCs: {len(surplus)}")


if __name__ == "__main__":
    main()
