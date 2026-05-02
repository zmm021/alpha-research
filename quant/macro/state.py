from __future__ import annotations

import pandas as pd

from quant.common.constants import StructureScores
from quant.common.enums import MacroState
from quant.common.types import ConfigDict
from quant.common.schemas import StructureOutput

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
            float(r[StructureScores.MACRO_TREND_STRENGTH]),
            float(r[StructureScores.MACRO_RISK_PRESSURE]),
            cfg,
        ),
        axis=1,
    )

def compute_macro_state_output(
    structure_output: StructureOutput,
    config: ConfigDict,
) -> MacroState:
    cfg = config["state"]
    values = structure_output.values
    trend = float(values.get(StructureScores.MACRO_TREND_STRENGTH, 0.0))
    risk = float(values.get(StructureScores.MACRO_RISK_PRESSURE, 0.0))
    return _single_state(trend, risk, cfg)