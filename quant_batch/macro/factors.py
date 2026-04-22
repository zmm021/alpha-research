from __future__ import annotations

import pandas as pd

from quant.common.constants import Indicators, Factors, Contexts
from quant.common.types import ConfigDict


def compute_macro_factors(indicator_df: pd.DataFrame, config: ConfigDict) -> pd.DataFrame:

    cfg = config["factors"]

    out = pd.DataFrame(index=indicator_df.index)

    out[Factors.MACRO_TREND_FACTOR] = (
        cfg["trend_scale"] * indicator_df[Indicators.SPY_TREND_Z]
    )

    out[Factors.MACRO_VOLATILITY_FACTOR] = (
        cfg["vol_scale"] * indicator_df[Indicators.VIX_Z]
    )

    out[Factors.MACRO_CREDIT_RISK_FACTOR] = (
        cfg["credit_scale"] * indicator_df[Indicators.HY_OAS_Z]
    )

    return out


def compute_macro_contexts(factor_df: pd.DataFrame, config: ConfigDict) -> pd.DataFrame:

    cfg = config["contexts"]

    out = pd.DataFrame(index=factor_df.index)

    trend = factor_df[Factors.MACRO_TREND_FACTOR]
    vol = factor_df[Factors.MACRO_VOLATILITY_FACTOR]
    credit = factor_df[Factors.MACRO_CREDIT_RISK_FACTOR]

    out[Contexts.MACRO_TREND_STRENGTH] = trend

    out[Contexts.MACRO_RISK_PRESSURE] = (
        cfg["vol_weight"] * vol.clip(lower=0) +
        cfg["credit_weight"] * credit.clip(lower=0)
    )

    return out