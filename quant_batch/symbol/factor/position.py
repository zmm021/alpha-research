from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators


def compute_position_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    position_scale = float(factor_cfg["position_scale"])

    distance_to_high = indicator_df[Indicators.DISTANCE_TO_HIGH]
    range_position = indicator_df[Indicators.RANGE_POSITION]

    out = pd.DataFrame(index=indicator_df.index)

    out[Factors.SYMBOL_POSITION_FACTOR] = position_scale * (-distance_to_high)
    out[Factors.SYMBOL_RANGE_POSITION_FACTOR] = range_position.clip(0.0, 1.0)

    return out