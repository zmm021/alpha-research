from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts
from quant.common.enums import MacroState
from quant.common.schemas import ContextOutput
from quant.common.types import ConfigDict


def _compute_single_macro_state(
    trend_strength: float,
    risk_pressure: float,
    config: ConfigDict,
) -> MacroState:
    """
    Phase-1 macro state logic:

    - RISK_OFF: risk pressure too high
    - RISK_ON: trend strong enough and risk low enough
    - otherwise NEUTRAL
    """
    state_cfg = config["state"]

    # 保留 fallback，增强工程安全
    risk_off_threshold = float(state_cfg.get("risk_off_threshold", 0.7))
    risk_on_max_risk = float(state_cfg.get("risk_on_max_risk", 0.4))
    risk_on_trend_threshold = float(state_cfg.get("risk_on_trend_threshold", 0.2))

    if risk_pressure >= risk_off_threshold:
        return MacroState.RISK_OFF

    if (
        trend_strength >= risk_on_trend_threshold
        and risk_pressure <= risk_on_max_risk
    ):
        return MacroState.RISK_ON

    return MacroState.NEUTRAL


def compute_macro_states(
    context_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    """
    Compute macro state series from macro contexts.
    """
    required_cols = [
        Contexts.MACRO_TREND_STRENGTH,
        Contexts.MACRO_RISK_PRESSURE,
    ]
    missing = [c for c in required_cols if c not in context_df.columns]
    if missing:
        raise ValueError(f"Missing required context columns for macro state: {missing}")

    return context_df.apply(
        lambda row: _compute_single_macro_state(
            trend_strength=float(row[Contexts.MACRO_TREND_STRENGTH]),
            risk_pressure=float(row[Contexts.MACRO_RISK_PRESSURE]),
            config=config,
        ),
        axis=1,
    )


def compute_macro_state_output(
    context_output: ContextOutput,
    config: ConfigDict,
) -> MacroState:
    """
    Convenience helper for latest-row / snapshot use cases.
    """
    values = context_output.values

    return _compute_single_macro_state(
        trend_strength=float(values.get(Contexts.MACRO_TREND_STRENGTH, 0.0)),
        risk_pressure=float(values.get(Contexts.MACRO_RISK_PRESSURE, 0.0)),
        config=config,
    )