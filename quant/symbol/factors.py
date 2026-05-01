from __future__ import annotations

import pandas as pd

from quant.common.constants import Indicators
from quant.common.schemas import StructureOutput, FactorOutput
from quant.common.types import ConfigDict

from quant.symbol.factor.common import require_indicator_columns
from quant.symbol.factor.structure import compute_symbol_structure_frame
from quant.symbol.factor.intraday import compute_intraday_factors
from quant.symbol.factor.liquidity import compute_liquidity_factors
from quant.symbol.factor.position import compute_position_factors
from quant.symbol.factor.trend import compute_trend_factors
from quant.symbol.factor.volatility import compute_volatility_factors


def compute_symbol_factors(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    required_cols = [
        Indicators.MA20,
        Indicators.MA50,
        Indicators.MA20_SLOPE,
        Indicators.ATR_PCT,
        Indicators.DISTANCE_TO_HIGH,
        Indicators.VOLUME_RATIO,
        Indicators.GAP_PCT,
        Indicators.PRICE_VS_VWAP,
        Indicators.RANGE_POSITION,
    ]
    require_indicator_columns(indicator_df, required_cols)

    factor_cfg = config["factors"]

    out = pd.DataFrame(index=indicator_df.index)

    trend_df = compute_trend_factors(indicator_df, factor_cfg)
    volatility_df = compute_volatility_factors(indicator_df, factor_cfg)
    liquidity_df = compute_liquidity_factors(indicator_df, factor_cfg)
    position_df = compute_position_factors(indicator_df, factor_cfg)
    intraday_df = compute_intraday_factors(indicator_df, factor_cfg)

    out = (
        out.join(trend_df)
        .join(volatility_df)
        .join(liquidity_df)
        .join(position_df)
        .join(intraday_df)
    )

    return out


def compute_symbol_structure(
    factor_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    return compute_symbol_structure_frame(factor_df, config["structure"])


def compute_symbol_factor_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> FactorOutput:
    factor_df = compute_symbol_factors(indicator_df, config)
    latest = factor_df.iloc[-1].dropna().to_dict()
    return FactorOutput(values={k: float(v) for k, v in latest.items()})


def compute_symbol_structure_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> StructureOutput:
    factor_df = compute_symbol_factors(indicator_df, config)
    structure_df = compute_symbol_structure(factor_df, config)
    latest = structure_df.iloc[-1].dropna().to_dict()
    return StructureOutput(values={k: float(v) for k, v in latest.items()})