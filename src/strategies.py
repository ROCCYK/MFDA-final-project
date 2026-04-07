from __future__ import annotations

from datetime import date

import pandas as pd

from src.data import CONTRACT_SIZE_GBP, DOWN_PAYMENT_USD, FORWARD_QUOTES, FUTURES_QUOTES, OPTION_QUOTES


def _receipt_spot(forecast_df: pd.DataFrame, target_date: date, scenario: str) -> float:
    row = forecast_df.loc[forecast_df["settlement_date"] == pd.Timestamp(target_date)].iloc[0]
    return float(row[scenario])


def _build_result_frame(records: list[dict[str, float | str]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    numeric_columns = [
        "gbp_receipt",
        "spot_rate",
        "spot_usd",
        "hedge_usd",
        "premium_usd",
        "net_usd",
    ]
    for column in numeric_columns:
        df[column] = df[column].astype(float)
    return df


def evaluate_unhedged(receipts: pd.DataFrame, forecast_df: pd.DataFrame, scenario: str) -> pd.DataFrame:
    records = []
    for row in receipts.itertuples(index=False):
        spot_rate = _receipt_spot(forecast_df, row.settlement_date, scenario)
        spot_usd = row.amount_gbp * spot_rate
        records.append(
            {
                "strategy": "Unhedged",
                "receipt_label": row.label,
                "settlement_date": row.settlement_date,
                "gbp_receipt": row.amount_gbp,
                "spot_rate": spot_rate,
                "spot_usd": spot_usd,
                "hedge_usd": 0.0,
                "premium_usd": 0.0,
                "net_usd": spot_usd,
            }
        )
    return _build_result_frame(records)


def evaluate_forward(receipts: pd.DataFrame, forecast_df: pd.DataFrame, scenario: str) -> pd.DataFrame:
    records = []
    for row in receipts.itertuples(index=False):
        spot_rate = _receipt_spot(forecast_df, row.settlement_date, scenario)
        hedge_rate = FORWARD_QUOTES[row.settlement_date]
        hedge_usd = row.amount_gbp * hedge_rate
        records.append(
            {
                "strategy": "Forward",
                "receipt_label": row.label,
                "settlement_date": row.settlement_date,
                "gbp_receipt": row.amount_gbp,
                "spot_rate": spot_rate,
                "spot_usd": row.amount_gbp * spot_rate,
                "hedge_usd": hedge_usd,
                "premium_usd": 0.0,
                "net_usd": hedge_usd,
            }
        )
    return _build_result_frame(records)


def evaluate_futures(receipts: pd.DataFrame, forecast_df: pd.DataFrame, scenario: str) -> pd.DataFrame:
    records = []
    for row in receipts.itertuples(index=False):
        spot_rate = _receipt_spot(forecast_df, row.settlement_date, scenario)
        futures_info = FUTURES_QUOTES[row.settlement_date]
        contracts = max(1, round(row.amount_gbp / CONTRACT_SIZE_GBP))
        hedged_gbp = contracts * CONTRACT_SIZE_GBP
        residual_gbp = row.amount_gbp - hedged_gbp
        futures_pl = (futures_info["price"] - spot_rate) * hedged_gbp
        spot_usd = row.amount_gbp * spot_rate
        records.append(
            {
                "strategy": "Futures",
                "receipt_label": f"{row.label} ({contracts} {futures_info['contract_month']} contracts; residual {residual_gbp:,.0f} GBP)",
                "settlement_date": row.settlement_date,
                "gbp_receipt": row.amount_gbp,
                "spot_rate": spot_rate,
                "spot_usd": spot_usd,
                "hedge_usd": futures_pl,
                "premium_usd": 0.0,
                "net_usd": spot_usd + futures_pl,
            }
        )
    return _build_result_frame(records)


def evaluate_options(
    receipts: pd.DataFrame,
    forecast_df: pd.DataFrame,
    scenario: str,
    strike: float,
) -> pd.DataFrame:
    records = []
    for row in receipts.itertuples(index=False):
        spot_rate = _receipt_spot(forecast_df, row.settlement_date, scenario)
        put_premium = OPTION_QUOTES[strike][row.settlement_date]["put"]
        intrinsic_value = max(strike - spot_rate, 0.0)
        option_payoff = intrinsic_value * row.amount_gbp
        premium_usd = put_premium * row.amount_gbp
        spot_usd = row.amount_gbp * spot_rate
        records.append(
            {
                "strategy": "Options",
                "receipt_label": f"{row.label} (put strike {strike:.3f})",
                "settlement_date": row.settlement_date,
                "gbp_receipt": row.amount_gbp,
                "spot_rate": spot_rate,
                "spot_usd": spot_usd,
                "hedge_usd": option_payoff,
                "premium_usd": premium_usd,
                "net_usd": spot_usd + option_payoff - premium_usd,
            }
        )
    return _build_result_frame(records)


def summarize_strategy(result_df: pd.DataFrame) -> dict[str, float]:
    return {
        "future_receipts_usd": float(result_df["net_usd"].sum()),
        "down_payment_usd": float(DOWN_PAYMENT_USD),
        "total_usd": float(result_df["net_usd"].sum() + DOWN_PAYMENT_USD),
        "hedge_component_usd": float(result_df["hedge_usd"].sum() - result_df["premium_usd"].sum()),
    }
