from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts
from quant.common.enums import MacroState
from quant.common.types import ConfigDict


def _single_state(
    trend: float,
    risk: float,
    cfg: dict,
) -> MacroState:

    if risk >= cfg["risk_off_threshold"]:
        return MacroState.RISK_OFF

    if trend >= cfg["risk_on_trend_threshold"] and risk <= cfg["risk_on_max_risk"]:
        return MacroState.RISK_ON

    return MacroState.NEUTRAL


def compute_macro_states(
    context_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:

    cfg = config["state"]

    return context_df.apply(
        lambda r: _single_state(
            float(r[Contexts.MACRO_TREND_STRENGTH]),
            float(r[Contexts.MACRO_RISK_PRESSURE]),
            cfg,
        ),
        axis=1,
    )