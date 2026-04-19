from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators


def compute_volatility_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    volatility_scale = float(factor_cfg["volatility_scale"])

    out = pd.DataFrame(index=indicator_df.index)
    out[Factors.SYMBOL_VOLATILITY_FACTOR] = (
        volatility_scale * indicator_df[Indicators.ATR_PCT]
    )
    return out