from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators
from quant.symbol.factor.common import safe_sign


def compute_trend_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    trend_scale = float(factor_cfg["trend_scale"])
    trend_cross_weight = float(factor_cfg["trend_cross_weight"])
    trend_slope_weight = float(factor_cfg["trend_slope_weight"])

    ma20 = indicator_df[Indicators.MA20]
    ma50 = indicator_df[Indicators.MA50]
    ma20_slope = indicator_df[Indicators.MA20_SLOPE]

    ma_cross_signal = (ma20 > ma50).astype(float) * 2.0 - 1.0
    slope_direction = safe_sign(ma20_slope.fillna(0.0))

    out = pd.DataFrame(index=indicator_df.index)
    out[Factors.SYMBOL_TREND_FACTOR] = trend_scale * (
        trend_cross_weight * ma_cross_signal
        + trend_slope_weight * slope_direction
    )
    out[Factors.SYMBOL_TREND_SLOPE_FACTOR] = trend_scale * slope_direction
    return out