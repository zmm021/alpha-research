from __future__ import annotations

import pandas as pd

from quant.common.constants import Factors, Indicators


def compute_intraday_factors(
    indicator_df: pd.DataFrame,
    factor_cfg: dict,
) -> pd.DataFrame:
    intraday_scale = float(factor_cfg["intraday_scale"])
    intraday_gap_weight = float(factor_cfg["intraday_gap_weight"])
    intraday_vwap_weight = float(factor_cfg["intraday_vwap_weight"])

    gap_pct = indicator_df[Indicators.GAP_PCT]
    price_vs_vwap = indicator_df[Indicators.PRICE_VS_VWAP]

    out = pd.DataFrame(index=indicator_df.index)
    out[Factors.SYMBOL_INTRADAY_INTENT_FACTOR] = intraday_scale * (
        intraday_gap_weight * gap_pct
        + intraday_vwap_weight * price_vs_vwap
    )
    return out