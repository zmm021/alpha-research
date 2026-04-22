from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import pandas as pd


VALID_SIGNALS = {"buy", "sell", "reduce", "avoid", "hold"}


@dataclass(slots=True)
class SignalRun:
    signal: str
    start_idx: int
    end_idx: int

    @property
    def length(self) -> int:
        return self.end_idx - self.start_idx + 1


def _normalize_signal_value(value: Any) -> str:
    if value is None:
        return "hold"

    try:
        if pd.isna(value):
            return "hold"
    except Exception:
        pass

    if hasattr(value, "value"):
        value = value.value

    value = str(value).lower().strip()
    return value if value in VALID_SIGNALS else "hold"


def _extract_runs(signal: pd.Series) -> list[SignalRun]:
    normalized = signal.apply(_normalize_signal_value).tolist()

    if not normalized:
        return []

    runs: list[SignalRun] = []
    current_signal = normalized[0]
    run_start = 0

    for i in range(1, len(normalized)):
        if normalized[i] != current_signal:
            runs.append(
                SignalRun(
                    signal=current_signal,
                    start_idx=run_start,
                    end_idx=i - 1,
                )
            )
            current_signal = normalized[i]
            run_start = i

    runs.append(
        SignalRun(
            signal=current_signal,
            start_idx=run_start,
            end_idx=len(normalized) - 1,
        )
    )
    return runs


def _future_window(close: pd.Series, start_idx: int, horizon: int) -> pd.Series:
    end_idx = min(start_idx + horizon, len(close) - 1)
    return close.iloc[start_idx : end_idx + 1].astype(float)


def _future_stats(close: pd.Series, start_idx: int, horizon: int) -> dict[str, float]:
    window = _future_window(close, start_idx, horizon)

    if len(window) <= 1:
        return {
            "forward_return": 0.0,
            "max_upside": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
        }

    p0 = float(window.iloc[0])
    rel = window / p0 - 1.0

    forward_return = float(rel.iloc[-1])
    max_upside = float(rel.max())
    max_drawdown = float(rel.min())
    volatility = float(rel.diff().dropna().std()) if len(rel) > 2 else 0.0

    return {
        "forward_return": forward_return,
        "max_upside": max_upside,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
    }


def _run_weight(length: int) -> float:
    return sqrt(max(length, 1))


def _score_buy(stats: dict[str, float]) -> float:
    return (
        1.0 * stats["forward_return"]
        + 0.5 * stats["max_upside"]
        - 0.75 * abs(min(stats["max_drawdown"], 0.0))
    )


def _score_sell(stats: dict[str, float]) -> float:
    return (
        1.0 * (-stats["forward_return"])
        + 0.5 * abs(min(stats["max_drawdown"], 0.0))
        - 0.25 * max(stats["max_upside"], 0.0)
    )


def _score_reduce(stats: dict[str, float]) -> float:
    return (
        0.5 * (-stats["forward_return"])
        - 0.75 * max(stats["max_upside"], 0.0)
        + 0.75 * abs(min(stats["max_drawdown"], 0.0))
        + 0.25 * stats["volatility"]
    )


def _score_avoid(stats: dict[str, float]) -> float:
    return (
        0.75 * (-stats["forward_return"])
        - 0.5 * max(stats["max_upside"], 0.0)
        + 0.25 * abs(min(stats["max_drawdown"], 0.0))
        + 0.25 * stats["volatility"]
    )


def _score_hold(stats: dict[str, float]) -> float:
    return (
        0.25 * stats["forward_return"]
        - 0.35 * abs(min(stats["max_drawdown"], 0.0))
    )


def _score_run(signal_type: str, stats: dict[str, float]) -> float:
    if signal_type == "buy":
        return _score_buy(stats)
    if signal_type == "sell":
        return _score_sell(stats)
    if signal_type == "reduce":
        return _score_reduce(stats)
    if signal_type == "avoid":
        return _score_avoid(stats)
    return _score_hold(stats)


def evaluate_signal_sequence(
    bar_df: pd.DataFrame,
    action_signal: pd.Series | None = None,
    *,
    signal_col: str = "action_signal",
    close_col: str = "close",
    horizon: int = 10,
    skip_hold: bool = True,
) -> tuple[float, dict[str, Any]]:
    """
    Evaluate signal-engine output quality.

    Input:
        bar_df:
            DataFrame containing at least `close_col`, and optionally `signal_col`
        action_signal:
            Optional external signal series. If provided, overrides bar_df[signal_col]
        signal_col:
            Signal column name inside bar_df
        close_col:
            Close price column name inside bar_df
        horizon:
            Forward bars used for evaluation
        skip_hold:
            Whether hold-runs are excluded from total score

    Output:
        (final_score, details)
    """

    if bar_df is None or bar_df.empty:
        raise ValueError("bar_df is None or empty")

    if close_col not in bar_df.columns:
        raise ValueError(f"bar_df missing required close column: {close_col}")

    close = bar_df[close_col].astype(float).reset_index(drop=True)

    if action_signal is None:
        if signal_col not in bar_df.columns:
            raise ValueError(
                f"action_signal is None and bar_df missing signal column: {signal_col}"
            )
        signal = bar_df[signal_col].reset_index(drop=True)
    else:
        signal = action_signal.reset_index(drop=True)

    if len(close) != len(signal):
        raise ValueError("close series and action_signal must have same length")

    runs = _extract_runs(signal)

    total_weighted_score = 0.0
    total_weight = 0.0

    per_signal_score_sum = {k: 0.0 for k in VALID_SIGNALS}
    per_signal_weight_sum = {k: 0.0 for k in VALID_SIGNALS}
    per_signal_run_count = {k: 0 for k in VALID_SIGNALS}

    run_records: list[dict[str, Any]] = []

    for run in runs:
        if skip_hold and run.signal == "hold":
            continue

        stats = _future_stats(close, run.start_idx, horizon)
        base_score = _score_run(run.signal, stats)
        weight = _run_weight(run.length)
        weighted_score = base_score * weight

        total_weighted_score += weighted_score
        total_weight += weight

        per_signal_score_sum[run.signal] += weighted_score
        per_signal_weight_sum[run.signal] += weight
        per_signal_run_count[run.signal] += 1

        run_records.append(
            {
                "signal": run.signal,
                "start_idx": run.start_idx,
                "end_idx": run.end_idx,
                "length": run.length,
                "weight": weight,
                "forward_return": stats["forward_return"],
                "max_upside": stats["max_upside"],
                "max_drawdown": stats["max_drawdown"],
                "volatility": stats["volatility"],
                "base_score": base_score,
                "weighted_score": weighted_score,
            }
        )

    raw_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

    switch_count = max(len(runs) - 1, 0)
    switch_rate = switch_count / max(len(signal), 1)
    noise_penalty = 0.25 * switch_rate

    final_score = raw_score - noise_penalty

    per_signal_avg_score = {}
    for sig in VALID_SIGNALS:
        w = per_signal_weight_sum[sig]
        per_signal_avg_score[sig] = per_signal_score_sum[sig] / w if w > 0 else 0.0

    normalized_signal_counts = (
        signal.apply(_normalize_signal_value).value_counts(dropna=False).to_dict()
    )
    run_counts = pd.Series([r.signal for r in runs]).value_counts().to_dict() if runs else {}

    details = {
        "raw_score": raw_score,
        "noise_penalty": noise_penalty,
        "final_score": final_score,
        "switch_count": switch_count,
        "switch_rate": switch_rate,
        "signal_counts": normalized_signal_counts,
        "run_counts": run_counts,
        "per_signal_run_count": per_signal_run_count,
        "per_signal_avg_score": per_signal_avg_score,
        "runs": run_records,
    }

    return final_score, details