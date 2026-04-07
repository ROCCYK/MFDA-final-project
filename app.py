from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data import (
    CASE_BASE_DATE,
    CURRENT_SPOT,
    DOWN_PAYMENT_USD,
    OPTION_QUOTES,
    TIMELINE_EVENTS,
    load_receipts,
    load_spot_history,
)
from src.forecasting import SCENARIO_ORDER, build_forecast_frame
from src.strategies import (
    evaluate_forward,
    evaluate_futures,
    evaluate_options,
    evaluate_unhedged,
    summarize_strategy,
)
from src.ui_helpers import (
    build_recommendation,
    build_scenario_recommendations,
    build_timeline_frame,
    date_label,
    format_rate,
    format_usd,
)


st.set_page_config(page_title="Waffle Industries FX Hedge Analyzer", layout="wide")


def padded_range(values: pd.Series, pad_ratio: float = 0.15, min_pad: float = 0.001) -> list[float]:
    low = float(values.min())
    high = float(values.max())
    spread = high - low
    pad = max(spread * pad_ratio, min_pad)
    return [low - pad, high + pad]

st.title("Waffle Industries Forex Risk Management")
st.caption(
    "Interactive Streamlit case app for MFDA 5300 Group Project, Winter 2026. "
    "All figures are based on the assignment data provided in the PDF."
)

with st.expander("How to read this app", expanded=True):
    st.markdown(
        """
        This app compares how much **USD cash Waffle Industries could end up with** under different hedging choices.

        **What the scenarios mean**
        - **Low:** the British pound weakens more than expected, so each pound converts into fewer U.S. dollars.
        - **Base:** the most likely exchange-rate estimate from the selected forecasting method.
        - **High:** the British pound stays stronger or appreciates, so each pound converts into more U.S. dollars.

        **What the forecast methods mean**
        - **Moving Average:** uses the recent average GBP/USD level as a simple baseline and adds a volatility band around it.
        - **Time Trend:** fits a straight trend line through the historical data and extends that trend forward to May and July.
        - **Scenario Distribution:** uses recent daily changes in the exchange rate to build low, base, and high future outcomes.

        **What the hedging strategies mean**
        - **Unhedged:** Waffle does nothing and accepts whatever future spot exchange rate exists on each payment date.
        - **Forward:** Waffle locks in a fixed exchange rate today with the bank for each future GBP receipt.
        - **Futures:** Waffle uses exchange-traded GBP futures for protection, but contract sizing can create a small mismatch.
        - **Options:** Waffle buys GBP put protection, which creates a downside floor while still allowing upside if GBP strengthens.

        **How to interpret the results**
        - Higher **total USD proceeds** are better for Waffle.
        - A strategy with more certainty may be preferable even if it is not the absolute highest in every scenario.
        - The comparison charts show both the expected outcome and how much each strategy trails the current best one.
        """
    )

spot_history = load_spot_history()
receipts = load_receipts()
target_dates = list(receipts["settlement_date"])

with st.sidebar:
    st.header("Analysis Controls")
    forecast_method = st.selectbox(
        "Forecast method",
        ["Moving Average", "Time Trend", "Scenario Distribution"],
        index=0,
    )
    scenario = st.selectbox("Scenario", SCENARIO_ORDER, index=1)
    strike = st.selectbox("Option strike", sorted(OPTION_QUOTES.keys()), index=1, format_func=lambda x: f"{x:.3f}")
    show_notes = st.toggle("Show formulas and teaching notes", value=False)
    st.markdown(
        """
        **Quick guide**

        **Scenario**
        - `low`: weaker GBP, worse for unhedged USD proceeds
        - `base`: central estimate
        - `high`: stronger GBP, better for unhedged USD proceeds

        **Option strike**
        - Higher strike = more protection
        - Higher strike also usually = higher option premium
        """
    )

forecast_df = build_forecast_frame(spot_history, target_dates, forecast_method)

strategy_results = {
    "Unhedged": evaluate_unhedged(receipts, forecast_df, scenario),
    "Forward": evaluate_forward(receipts, forecast_df, scenario),
    "Futures": evaluate_futures(receipts, forecast_df, scenario),
    "Options": evaluate_options(receipts, forecast_df, scenario, strike),
}

summary_rows = []
for strategy_name, result_df in strategy_results.items():
    summary = summarize_strategy(result_df)
    summary_rows.append(
        {
            "strategy": strategy_name,
            "scenario": scenario,
            "future_receipts_usd": summary["future_receipts_usd"],
            "down_payment_usd": summary["down_payment_usd"],
            "total_usd": summary["total_usd"],
            "hedge_component_usd": summary["hedge_component_usd"],
        }
    )

base_summaries = []
for scenario_name in SCENARIO_ORDER:
    for strategy_name in strategy_results:
        if strategy_name == "Unhedged":
            scenario_df = evaluate_unhedged(receipts, forecast_df, scenario_name)
        elif strategy_name == "Forward":
            scenario_df = evaluate_forward(receipts, forecast_df, scenario_name)
        elif strategy_name == "Futures":
            scenario_df = evaluate_futures(receipts, forecast_df, scenario_name)
        else:
            scenario_df = evaluate_options(receipts, forecast_df, scenario_name, strike)
        summary = summarize_strategy(scenario_df)
        base_summaries.append(
            {
                "strategy": strategy_name,
                "scenario": scenario_name,
                "total_usd": summary["total_usd"],
            }
        )

summary_df = pd.DataFrame(summary_rows)
scenario_comparison_df = pd.DataFrame(base_summaries)
recommendation_title, recommendation_detail = build_recommendation(scenario_comparison_df)
scenario_recommendations = build_scenario_recommendations(scenario_comparison_df)

summary_df["total_label"] = summary_df["total_usd"].map(lambda value: f"${value/1_000_000:.3f}M")
scenario_comparison_df["total_label"] = scenario_comparison_df["total_usd"].map(
    lambda value: f"${value/1_000_000:.3f}M"
)

overview_col, metrics_col = st.columns([1.2, 1.8], gap="large")

with overview_col:
    st.subheader("Case Overview")
    st.markdown(
        f"""
        - Contract signed on **{CASE_BASE_DATE.strftime('%B %d, %Y')}**
        - Today's spot rate for the signed deal: **{CURRENT_SPOT:.2f} USD/GBP**
        - Down payment already converted: **{format_usd(DOWN_PAYMENT_USD)}**
        - Remaining exposure: **GBP 2,200,000** across May 20 and July 20 receipts
        """
    )
    timeline_df = build_timeline_frame(TIMELINE_EVENTS)
    st.dataframe(
        timeline_df.assign(date=timeline_df["date"].dt.strftime("%b %d, %Y")),
        use_container_width=True,
        hide_index=True,
    )

with metrics_col:
    st.subheader("Forecast Summary")
    st.caption(
        "These cards show the selected method's low, base, and high GBP/USD forecasts for each payment date."
    )
    metric_cols = st.columns(len(target_dates))
    for card_col, row in zip(metric_cols, forecast_df.itertuples(index=False)):
        with card_col:
            st.metric(f"{date_label(row.settlement_date.date())} base", format_rate(row.base))
            st.caption(f"Low {format_rate(row.low)} | High {format_rate(row.high)}")

spot_chart = px.line(
    spot_history,
    x="date",
    y="spot",
    title="Historical GBP/USD Spot Rate",
    markers=True,
)
event_labels = [
    {
        "date": pd.Timestamp("2026-04-18"),
        "spot": float(spot_history.loc[spot_history["date"] == pd.Timestamp("2026-04-18"), "spot"].iloc[0]),
        "label": "Apr 18: Last historical spot",
        "text_position": "top left",
    },
    {
        "date": pd.Timestamp("2026-04-20"),
        "spot": CURRENT_SPOT,
        "label": "Apr 20: Contract signed and GBP500k converted",
        "text_position": "top right",
    },
    {
        "date": pd.Timestamp("2026-05-20"),
        "spot": float(forecast_df.loc[forecast_df["settlement_date"] == pd.Timestamp("2026-05-20"), "base"].iloc[0]),
        "label": "May 20: GBP700k receipt",
        "text_position": "top center",
    },
    {
        "date": pd.Timestamp("2026-07-20"),
        "spot": float(forecast_df.loc[forecast_df["settlement_date"] == pd.Timestamp("2026-07-20"), "base"].iloc[0]),
        "label": "Jul 20: GBP1.5M receipt",
        "text_position": "top center",
    },
]
event_df = pd.DataFrame(event_labels)
best_spot_row = spot_history.loc[spot_history["spot"].idxmax()]

spot_chart.add_scatter(
    x=event_df["date"],
    y=event_df["spot"],
    mode="markers+text",
    text=event_df["label"],
    textposition=event_df["text_position"],
    marker=dict(size=12, color="#ffb703", symbol="diamond"),
    name="Case events",
    hovertemplate="%{text}<br>%{x|%b %d, %Y}<br>Rate: %{y:.4f} USD/GBP<extra></extra>",
)
for event in event_labels:
    spot_chart.add_vline(
        x=event["date"],
        line_dash="dot",
        line_color="#ffb703",
        opacity=0.45,
    )
spot_chart.add_scatter(
    x=[best_spot_row["date"]],
    y=[best_spot_row["spot"]],
    mode="markers",
    marker=dict(size=14, color="#22c55e", symbol="star"),
    name="Best historical rate",
    hovertemplate="Best historical GBP/USD for Waffle<br>%{x|%b %d, %Y}<br>Rate: %{y:.4f} USD/GBP<extra></extra>",
)
spot_chart.add_annotation(
    x=best_spot_row["date"],
    y=best_spot_row["spot"],
    text="BEST historical rate",
    showarrow=True,
    arrowhead=2,
    ax=80,
    ay=30,
    bgcolor="rgba(34,197,94,0.16)",
    bordercolor="#22c55e",
    font=dict(color="#d1fae5", size=11),
)
spot_chart.update_layout(yaxis_title="USD per GBP", xaxis_title="")
st.plotly_chart(spot_chart, use_container_width=True)
st.caption("On FX-rate charts, `best` means the highest USD per GBP because Waffle is receiving pounds and wants them to convert into more U.S. dollars.")

forecast_chart_df = forecast_df.melt(
    id_vars=["settlement_date", "method"],
    value_vars=SCENARIO_ORDER,
    var_name="scenario",
    value_name="spot_rate",
)
forecast_chart_df["spot_label"] = forecast_chart_df["spot_rate"].map(lambda value: f"{value:.4f}")
forecast_chart = px.bar(
    forecast_chart_df,
    x="settlement_date",
    y="spot_rate",
    color="scenario",
    text="spot_label",
    barmode="group",
    title=f"{forecast_method} Forecast by Scenario",
)
forecast_chart.update_traces(textposition="outside")
best_forecast = forecast_chart_df.loc[forecast_chart_df["spot_rate"].idxmax()]
forecast_chart.add_scatter(
    x=[best_forecast["settlement_date"]],
    y=[best_forecast["spot_rate"]],
    mode="markers",
    marker=dict(size=16, color="#22c55e", symbol="star"),
    name="Best forecast outcome",
    hovertemplate="BEST forecast<br>%{x|%b %d, %Y}<br>Rate: %{y:.4f} USD/GBP<extra></extra>",
)
forecast_chart.add_annotation(
    x=best_forecast["settlement_date"],
    y=best_forecast["spot_rate"],
    text=f"BEST forecast<br>{best_forecast['scenario']}",
    showarrow=True,
    arrowhead=2,
    ax=0,
    ay=-52,
    bgcolor="rgba(34,197,94,0.16)",
    bordercolor="#22c55e",
    font=dict(color="#d1fae5", size=11),
)
forecast_chart.update_layout(
    yaxis_title="USD per GBP",
    xaxis_title="",
    yaxis_range=padded_range(forecast_chart_df["spot_rate"], pad_ratio=0.25, min_pad=0.002),
)
st.plotly_chart(forecast_chart, use_container_width=True)

st.subheader("Strategy Comparison")
st.caption(
    "This table summarizes each strategy's projected future receipts, the fixed USD down payment already received, and total USD proceeds."
)
comparison_view = summary_df.copy()
comparison_view["future_receipts_usd"] = comparison_view["future_receipts_usd"].map(format_usd)
comparison_view["down_payment_usd"] = comparison_view["down_payment_usd"].map(format_usd)
comparison_view["hedge_component_usd"] = comparison_view["hedge_component_usd"].map(format_usd)
comparison_view["total_usd"] = comparison_view["total_usd"].map(format_usd)
st.dataframe(comparison_view, use_container_width=True, hide_index=True)

proceeds_chart = px.bar(
    summary_df,
    x="strategy",
    y="total_usd",
    color="strategy",
    text="total_label",
    title=f"Projected Total USD Proceeds ({scenario.capitalize()} scenario)",
)
proceeds_chart.update_traces(textposition="outside")
best_strategy_row = summary_df.loc[summary_df["total_usd"].idxmax()]
proceeds_chart.add_scatter(
    x=[best_strategy_row["strategy"]],
    y=[best_strategy_row["total_usd"]],
    mode="markers",
    marker=dict(size=16, color="#22c55e", symbol="star"),
    name="Best strategy",
    hovertemplate="Best strategy<br>%{x}<br>Total: $%{y:,.0f}<extra></extra>",
)
proceeds_chart.add_annotation(
    x=best_strategy_row["strategy"],
    y=best_strategy_row["total_usd"],
    text="BEST strategy",
    showarrow=True,
    arrowhead=2,
    ax=0,
    ay=-52,
    bgcolor="rgba(34,197,94,0.16)",
    bordercolor="#22c55e",
    font=dict(color="#d1fae5", size=11),
)
proceeds_chart.update_layout(
    showlegend=False,
    yaxis_title="USD proceeds",
    xaxis_title="",
    yaxis_range=padded_range(summary_df["total_usd"], pad_ratio=0.2, min_pad=10_000),
)
st.plotly_chart(proceeds_chart, use_container_width=True)

best_total = float(summary_df["total_usd"].max())
delta_view = summary_df.copy()
delta_view["gap_to_best"] = best_total - delta_view["total_usd"]
delta_view["gap_label"] = delta_view["gap_to_best"].map(lambda value: f"${value:,.0f}")
delta_chart = px.bar(
    delta_view.sort_values("gap_to_best"),
    x="strategy",
    y="gap_to_best",
    color="strategy",
    text="gap_label",
    title="How Far Each Strategy Is From the Best Outcome",
)
delta_chart.update_traces(textposition="outside")
best_gap_row = delta_view.loc[delta_view["gap_to_best"].idxmin()]
delta_chart.add_scatter(
    x=[best_gap_row["strategy"]],
    y=[best_gap_row["gap_to_best"]],
    mode="markers",
    marker=dict(size=16, color="#22c55e", symbol="star"),
    name="Best gap",
    hovertemplate="Best strategy in gap view<br>%{x}<br>Gap: $%{y:,.0f}<extra></extra>",
)
delta_chart.add_annotation(
    x=best_gap_row["strategy"],
    y=best_gap_row["gap_to_best"],
    text="BEST<br>smallest gap",
    showarrow=True,
    arrowhead=2,
    ax=0,
    ay=-48,
    bgcolor="rgba(34,197,94,0.16)",
    bordercolor="#22c55e",
    font=dict(color="#d1fae5", size=11),
)
delta_chart.update_layout(
    showlegend=False,
    yaxis_title="USD below best strategy",
    xaxis_title="",
    yaxis_range=[0, max(float(delta_view["gap_to_best"].max()) * 1.25, 10_000)],
)
st.plotly_chart(delta_chart, use_container_width=True)
st.caption(
    "The gap chart is a ranking aid: `0` means that strategy is currently the best outcome under the selected scenario."
)

scenario_chart = px.bar(
    scenario_comparison_df,
    x="strategy",
    y="total_usd",
    color="scenario",
    text="total_label",
    barmode="group",
    title="Low/Base/High Scenario Comparison",
)
scenario_chart.update_traces(textposition="outside")
best_by_scenario = (
    scenario_comparison_df.sort_values(["scenario", "total_usd"], ascending=[True, False])
    .groupby("scenario", as_index=False)
    .first()
)
scenario_chart.add_scatter(
    x=best_by_scenario["strategy"],
    y=best_by_scenario["total_usd"],
    mode="markers",
    marker=dict(size=16, color="#22c55e", symbol="star"),
    name="Best by scenario",
    hovertemplate="Best strategy for %{customdata}<br>%{x}<br>Total: $%{y:,.0f}<extra></extra>",
    customdata=best_by_scenario["scenario"],
)
annotation_offsets = {"low": (-40, -55), "base": (0, -82), "high": (40, -55)}
for row in best_by_scenario.itertuples(index=False):
    ax, ay = annotation_offsets[row.scenario]
    scenario_chart.add_annotation(
        x=row.strategy,
        y=row.total_usd,
        text=f"BEST<br>{row.scenario}",
        showarrow=True,
        arrowhead=2,
        ax=ax,
        ay=ay,
        bgcolor="rgba(34,197,94,0.16)",
        bordercolor="#22c55e",
        font=dict(color="#d1fae5", size=11),
    )
scenario_chart.update_layout(
    yaxis_title="USD proceeds",
    xaxis_title="",
    yaxis_range=padded_range(scenario_comparison_df["total_usd"], pad_ratio=0.2, min_pad=10_000),
)
st.plotly_chart(scenario_chart, use_container_width=True)
st.caption(
    "This scenario chart shows how each strategy behaves if GBP turns out weaker, close to expectations, or stronger than expected."
)

st.subheader("Per-Strategy Cash Flow Detail")
st.caption("Open each tab to see how the May and July receipts are converted into USD under that specific hedge choice.")
tabs = st.tabs(list(strategy_results.keys()))
for tab, (strategy_name, result_df) in zip(tabs, strategy_results.items()):
    with tab:
        detail_view = result_df.copy()
        detail_view["settlement_date"] = pd.to_datetime(detail_view["settlement_date"]).dt.strftime("%b %d, %Y")
        detail_view["spot_rate"] = detail_view["spot_rate"].map(format_rate)
        for column in ["spot_usd", "hedge_usd", "premium_usd", "net_usd"]:
            detail_view[column] = detail_view[column].map(format_usd)
        st.dataframe(detail_view, use_container_width=True, hide_index=True)

st.subheader("Combined Summary Table")
st.caption(
    "This table combines every strategy across low, base, and high scenarios so you can compare total USD proceeds, hedge impact, and the current scenario winner in one place."
)
combined_summary_df = scenario_comparison_df.merge(
    summary_df[["strategy", "future_receipts_usd", "down_payment_usd", "hedge_component_usd"]],
    on="strategy",
    how="left",
)
best_total_by_scenario = combined_summary_df.groupby("scenario")["total_usd"].transform("max")
combined_summary_df["is_best"] = combined_summary_df["total_usd"].eq(best_total_by_scenario).map(
    lambda is_best: "Yes" if is_best else ""
)
scenario_display = {"low": "Low", "base": "Base", "high": "High"}
combined_summary_view = combined_summary_df.copy()
combined_summary_view["scenario"] = combined_summary_view["scenario"].map(scenario_display)
combined_summary_view["future_receipts_usd"] = combined_summary_view["future_receipts_usd"].map(format_usd)
combined_summary_view["down_payment_usd"] = combined_summary_view["down_payment_usd"].map(format_usd)
combined_summary_view["hedge_component_usd"] = combined_summary_view["hedge_component_usd"].map(format_usd)
combined_summary_view["total_usd"] = combined_summary_view["total_usd"].map(format_usd)
combined_summary_view = combined_summary_view.rename(
    columns={
        "scenario": "scenario",
        "strategy": "strategy",
        "future_receipts_usd": "future_receipts_usd",
        "down_payment_usd": "down_payment_usd",
        "hedge_component_usd": "hedge_component_usd",
        "total_usd": "total_usd",
        "is_best": "best_in_scenario",
    }
)
st.dataframe(
    combined_summary_view[
        [
            "scenario",
            "strategy",
            "future_receipts_usd",
            "down_payment_usd",
            "hedge_component_usd",
            "total_usd",
            "best_in_scenario",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Recommendation")
st.success(recommendation_title)
st.write(recommendation_detail)
st.caption("The base-case recommendation is shown first, followed by the best strategy under each scenario.")

recommendation_columns = st.columns(3)
status_styles = {
    "low": st.warning,
    "base": st.success,
    "high": st.info,
}
for column, row in zip(recommendation_columns, scenario_recommendations.itertuples(index=False)):
    with column:
        status_styles[row.scenario](f"{row.scenario_label}: {row.strategy}")
        st.write(row.detail)

if show_notes:
    st.subheader("Formulas and Teaching Notes")
    st.markdown(
        """
        - **Unhedged:** future USD proceeds = `GBP receipt x forecast spot`.
        - **Forward hedge:** future USD proceeds = `GBP receipt x quoted forward rate`.
        - **Futures hedge:** short GBP futures because Waffle will receive pounds later and loses when GBP weakens.
        - **Futures P/L approximation:** `(entry futures - settlement spot) x hedged GBP`.
        - **Options hedge:** buy GBP puts to create a floor while preserving upside from stronger GBP.
        - **Options net proceeds:** `spot conversion + put payoff - premium`.
        - The May receipt cannot be perfectly matched with futures because `GBP700,000 / 62,500 = 11.2` contracts, so the app rounds to the nearest whole contract and shows the residual exposure.
        """
    )
