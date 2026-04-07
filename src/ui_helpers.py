from __future__ import annotations

from datetime import date

import pandas as pd


def format_usd(value: float) -> str:
    return f"${value:,.0f}"


def format_rate(value: float) -> str:
    return f"{value:.4f}"


def build_recommendation(summary_df: pd.DataFrame) -> tuple[str, str]:
    base_view = summary_df.loc[summary_df["scenario"] == "base"].copy()
    best_row = base_view.sort_values("total_usd", ascending=False).iloc[0]
    notes = {
        "Unhedged": "highest upside if GBP strengthens, but it leaves the firm fully exposed to a weaker pound.",
        "Forward": "locks in proceeds cleanly and removes FX uncertainty, but gives up upside from a stronger pound.",
        "Futures": "provides strong protection with exchange-traded contracts, though basis risk and contract rounding create small mismatches.",
        "Options": "sets a floor under USD proceeds while preserving upside, but the premium lowers expected cash inflow.",
    }
    title = f"Recommended under the base scenario: {best_row['strategy']}"
    detail = (
        f"{best_row['strategy']} produces the highest projected total USD proceeds at "
        f"{best_row['total_usd']:,.0f}. Tradeoff: it {notes[best_row['strategy']]}"
    )
    return title, detail


def build_scenario_recommendations(summary_df: pd.DataFrame) -> pd.DataFrame:
    notes = {
        "Unhedged": "best only if Waffle is comfortable staying fully exposed to GBP movements.",
        "Forward": "best when certainty and locked-in proceeds matter most.",
        "Futures": "best when Waffle wants hedge protection with exchange-traded contracts and accepts a small mismatch risk.",
        "Options": "best when Waffle wants downside protection while still keeping upside if GBP strengthens.",
    }
    labels = {
        "low": "Low scenario",
        "base": "Base scenario",
        "high": "High scenario",
    }

    rows = []
    for scenario in ["low", "base", "high"]:
        scenario_view = summary_df.loc[summary_df["scenario"] == scenario].copy()
        best_row = scenario_view.sort_values("total_usd", ascending=False).iloc[0]
        rows.append(
            {
                "scenario": scenario,
                "scenario_label": labels[scenario],
                "strategy": best_row["strategy"],
                "total_usd": best_row["total_usd"],
                "detail": (
                    f"{best_row['strategy']} has the highest projected total at ${best_row['total_usd']:,.0f} "
                    f"and is {notes[best_row['strategy']]}"
                ),
            }
        )

    return pd.DataFrame(rows)


def build_timeline_frame(events: list[tuple[str, str]]) -> pd.DataFrame:
    timeline = pd.DataFrame(events, columns=["date", "event"])
    timeline["date"] = pd.to_datetime(timeline["date"])
    return timeline


def date_label(value: date) -> str:
    return pd.Timestamp(value).strftime("%b %d, %Y")
