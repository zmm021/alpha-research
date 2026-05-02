from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators


def compute_position_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    position_scale = float(factor_cfg["position_scale"])

    distance_to_high_short = pd.to_numeric(
        indicator_df[Indicators.DISTANCE_TO_HIGH_SHORT],
        errors="coerce",
    )
    distance_to_high_mid = pd.to_numeric(
        indicator_df[Indicators.DISTANCE_TO_HIGH_MID],
        errors="coerce",
    )
    range_position_short = pd.to_numeric(
        indicator_df[Indicators.RANGE_POSITION_SHORT],
        errors="coerce",
    )
    range_position_mid = pd.to_numeric(
        indicator_df[Indicators.RANGE_POSITION_MID],
        errors="coerce",
    )

    out = pd.DataFrame(index=indicator_df.index)

    out[Factors.SYMBOL_POSITION_FACTOR_SHORT] = (
        position_scale * (-distance_to_high_short)
    )
    out[Factors.SYMBOL_POSITION_FACTOR_MID] = (
        position_scale * (-distance_to_high_mid)
    )

    out[Factors.SYMBOL_RANGE_POSITION_FACTOR_SHORT] = (
        range_position_short.clip(0.0, 1.0)
    )
    out[Factors.SYMBOL_RANGE_POSITION_FACTOR_MID] = (
        range_position_mid.clip(0.0, 1.0)
    )

    return out