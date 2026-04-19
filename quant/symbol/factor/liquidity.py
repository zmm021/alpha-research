from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators


def compute_liquidity_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    liquidity_scale = float(factor_cfg["liquidity_scale"])

    out = pd.DataFrame(index=indicator_df.index)
    out[Factors.SYMBOL_LIQUIDITY_FACTOR] = (
        liquidity_scale * indicator_df[Indicators.VOLUME_RATIO]
    )
    return out