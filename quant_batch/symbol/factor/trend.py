from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators
from quant.symbol.factor.common import safe_sign


def compute_trend_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    """
    Trend factor layer

    Existing outputs:
        - SYMBOL_TREND_FACTOR
        - SYMBOL_TREND_SLOPE_FACTOR

    New outputs:
        - symbol_trend_slope_raw   (continuous short slope)
        - symbol_long_slope_raw    (continuous long slope)

    Notes:
        - factor 层继续保留离散方向型 factor，兼容现有 state / signal
        - 同时补充连续 slope，供 regime_quality / decision 使用
    """

    trend_scale = float(factor_cfg["trend_scale"])
    trend_cross_weight = float(factor_cfg["trend_cross_weight"])
    trend_slope_weight = float(factor_cfg["trend_slope_weight"])

    ma20 = indicator_df[Indicators.MA20]
    ma50 = indicator_df[Indicators.MA50]
    ma20_slope = indicator_df[Indicators.MA20_SLOPE]

    # 新增：长期 slope
    if Indicators.MA50_SLOPE not in indicator_df.columns:
        raise ValueError(f"Missing required indicator column: {Indicators.MA50_SLOPE}")
    ma50_slope = indicator_df[Indicators.MA50_SLOPE]

    # ----------------------
    # 原有离散趋势逻辑
    # ----------------------
    ma_cross_signal = (ma20 > ma50).astype(float) * 2.0 - 1.0
    slope_direction = safe_sign(ma20_slope.fillna(0.0))

    out = pd.DataFrame(index=indicator_df.index)

    out[Factors.SYMBOL_TREND_FACTOR] = trend_scale * (
        trend_cross_weight * ma_cross_signal
        + trend_slope_weight * slope_direction
    )

    out[Factors.SYMBOL_TREND_SLOPE_FACTOR] = trend_scale * slope_direction

    # ----------------------
    # 新增：连续 slope 原始值
    # 供 regime_quality / decision 使用
    # ----------------------
    out["symbol_trend_slope_raw"] = ma20_slope.fillna(0.0)
    out["symbol_long_slope_raw"] = ma50_slope.fillna(0.0)

    return out