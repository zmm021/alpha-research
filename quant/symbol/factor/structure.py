from __future__ import annotations

import pandas as pd

from quant.common.constants import StructureScores, Factors
from quant.symbol.factor.common import require_factor_columns


def compute_symbol_structure_frame(
    factor_df: pd.DataFrame,
    structure_cfg: dict,
) -> pd.DataFrame:
    required_cols = [
        Factors.SYMBOL_TREND_FACTOR,
        Factors.SYMBOL_TREND_SLOPE_FACTOR,
        Factors.SYMBOL_VOLATILITY_FACTOR,
        Factors.SYMBOL_LIQUIDITY_FACTOR,
        Factors.SYMBOL_POSITION_FACTOR_SHORT,
        Factors.SYMBOL_POSITION_FACTOR_MID,
        Factors.SYMBOL_RANGE_POSITION_FACTOR_SHORT,
        Factors.SYMBOL_RANGE_POSITION_FACTOR_MID,
        Factors.SYMBOL_INTRADAY_INTENT_FACTOR,
    ]
    require_factor_columns(factor_df, required_cols)

    exhaustion_position_weight = float(structure_cfg["exhaustion_position_weight"])
    exhaustion_intraday_weight = float(structure_cfg["exhaustion_intraday_weight"])

    failure_vol_weight = float(structure_cfg["failure_vol_weight"])
    failure_intraday_weight = float(structure_cfg["failure_intraday_weight"])

    out = pd.DataFrame(index=factor_df.index)

    trend_factor = factor_df[Factors.SYMBOL_TREND_FACTOR]
    trend_slope_factor = factor_df[Factors.SYMBOL_TREND_SLOPE_FACTOR]
    volatility_factor = factor_df[Factors.SYMBOL_VOLATILITY_FACTOR]
    liquidity_factor = factor_df[Factors.SYMBOL_LIQUIDITY_FACTOR]

    position_factor_short = factor_df[Factors.SYMBOL_POSITION_FACTOR_SHORT]
    position_factor_mid = factor_df[Factors.SYMBOL_POSITION_FACTOR_MID]

    range_position_factor_short = factor_df[Factors.SYMBOL_RANGE_POSITION_FACTOR_SHORT]
    range_position_factor_mid = factor_df[Factors.SYMBOL_RANGE_POSITION_FACTOR_MID]

    intraday_factor = factor_df[Factors.SYMBOL_INTRADAY_INTENT_FACTOR]

    out[StructureScores.SYMBOL_TREND_STRENGTH] = trend_factor
    out[StructureScores.SYMBOL_TREND_SLOPE] = trend_slope_factor
    out[StructureScores.SYMBOL_VOLATILITY_STATE] = volatility_factor
    out[StructureScores.SYMBOL_INTRADAY_INTENT] = intraday_factor
    out[StructureScores.SYMBOL_LIQUIDITY_QUALITY] = liquidity_factor

    out[StructureScores.SYMBOL_POSITION_QUALITY_SHORT] = position_factor_short
    out[StructureScores.SYMBOL_POSITION_QUALITY_MID] = position_factor_mid

    out[StructureScores.SYMBOL_RANGE_POSITION_SHORT] = range_position_factor_short
    out[StructureScores.SYMBOL_RANGE_POSITION_MID] = range_position_factor_mid

    out[StructureScores.SYMBOL_EXHAUSTION_RISK] = (
        exhaustion_position_weight * position_factor_short.clip(lower=0.0)
        + exhaustion_intraday_weight * intraday_factor.clip(lower=0.0)
    )

    out[StructureScores.SYMBOL_FAILURE_RISK] = (
        failure_vol_weight * volatility_factor.clip(lower=0.0)
        + failure_intraday_weight * (-intraday_factor).clip(lower=0.0)
    )

    out[StructureScores.SYMBOL_REVERSAL_PRESSURE] = (
        (-trend_slope_factor).clip(lower=0.0)
        + (-intraday_factor).clip(lower=0.0)
    ) / 2.0

    return out