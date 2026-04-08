from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


SCENARIO_ORDER = ["low", "base", "high"]


def _clip_and_sort(values: dict[str, float]) -> dict[str, float]:
    low = max(values["low"], 0.01)
    base = max(values["base"], 0.01)
    high = max(values["high"], 0.01)
    ordered = sorted([low, base, high])
    return {"low": ordered[0], "base": ordered[1], "high": ordered[2]}


def _history_with_anchor(
    history: pd.DataFrame,
    anchor_date: date | None = None,
    anchor_spot: float | None = None,
) -> pd.DataFrame:
    anchored_history = history.copy()
    if anchor_date is not None and anchor_spot is not None:
        anchor_timestamp = pd.Timestamp(anchor_date)
        anchored_history = anchored_history.loc[anchored_history["date"] != anchor_timestamp]
        anchored_history = pd.concat(
            [
                anchored_history,
                pd.DataFrame([{"date": anchor_timestamp, "spot": float(anchor_spot)}]),
            ],
            ignore_index=True,
        )
    return anchored_history.sort_values("date").reset_index(drop=True)


def moving_average_forecast(
    history: pd.DataFrame,
    targets: list[date],
    window: int = 10,
    vol_window: int = 20,
) -> dict[date, dict[str, float]]:
    recent_spots = history["spot"].tail(window)
    base_level = float(recent_spots.mean())
    returns = history["spot"].pct_change().dropna().tail(vol_window)
    daily_vol = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    anchor_date = history["date"].max().date()

    forecasts: dict[date, dict[str, float]] = {}
    for target in targets:
        horizon_days = max((target - anchor_date).days, 1)
        vol_band = base_level * daily_vol * np.sqrt(horizon_days)
        forecasts[target] = _clip_and_sort(
            {
                "low": base_level - vol_band,
                "base": base_level,
                "high": base_level + vol_band,
            }
        )
    return forecasts


def trend_forecast(history: pd.DataFrame, targets: list[date]) -> dict[date, dict[str, float]]:
    x = np.arange(len(history))
    y = history["spot"].to_numpy()
    slope, intercept = np.polyfit(x, y, deg=1)
    fitted = intercept + slope * x
    residual_std = float(np.std(y - fitted, ddof=1)) if len(history) > 2 else 0.0
    anchor_date = history["date"].max().date()
    last_index = len(history) - 1

    forecasts: dict[date, dict[str, float]] = {}
    for target in targets:
        horizon_days = max((target - anchor_date).days, 1)
        horizon_trading_days = max(round(horizon_days * 5 / 7), 1)
        target_index = last_index + horizon_trading_days
        base_level = float(intercept + slope * target_index)
        band = residual_std * (1 + horizon_days / 60)
        forecasts[target] = _clip_and_sort(
            {
                "low": base_level - band,
                "base": base_level,
                "high": base_level + band,
            }
        )
    return forecasts


def scenario_distribution_forecast(
    history: pd.DataFrame,
    targets: list[date],
    lookback: int = 30,
) -> dict[date, dict[str, float]]:
    recent = history.tail(lookback).copy()
    current_spot = float(recent["spot"].iloc[-1])
    returns = recent["spot"].pct_change().dropna()
    mean_return = float(returns.mean()) if not returns.empty else 0.0
    low_quantile = float(returns.quantile(0.2)) if not returns.empty else 0.0
    high_quantile = float(returns.quantile(0.8)) if not returns.empty else 0.0
    anchor_date = recent["date"].max().date()

    forecasts: dict[date, dict[str, float]] = {}
    for target in targets:
        horizon_days = max((target - anchor_date).days, 1)
        forecasts[target] = _clip_and_sort(
            {
                "low": current_spot * ((1 + low_quantile) ** horizon_days),
                "base": current_spot * ((1 + mean_return) ** horizon_days),
                "high": current_spot * ((1 + high_quantile) ** horizon_days),
            }
        )
    return forecasts


def build_forecast_frame(
    history: pd.DataFrame,
    targets: list[date],
    method_name: str,
    anchor_date: date | None = None,
    anchor_spot: float | None = None,
) -> pd.DataFrame:
    method_map = {
        "Moving Average": moving_average_forecast,
        "Time Trend": trend_forecast,
        "Scenario Distribution": scenario_distribution_forecast,
    }
    forecast_fn = method_map[method_name]
    forecast_history = _history_with_anchor(history, anchor_date=anchor_date, anchor_spot=anchor_spot)
    forecast_dict = forecast_fn(forecast_history, targets)

    rows = []
    for target in targets:
        scenarios = forecast_dict[target]
        rows.append(
            {
                "settlement_date": pd.Timestamp(target),
                "low": scenarios["low"],
                "base": scenarios["base"],
                "high": scenarios["high"],
                "method": method_name,
            }
        )

    return pd.DataFrame(rows)
