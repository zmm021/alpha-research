from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts, Factors, Indicators
from quant.common.schemas import ContextOutput, FactorOutput
from quant.common.types import ConfigDict


def compute_macro_factors(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    """
    Compute phase-1 macro factors from macro indicators.
    """
    required_cols = [
        Indicators.SPY_TREND_Z,
        Indicators.VIX_Z,
        Indicators.HY_OAS_Z,
    ]
    missing = [c for c in required_cols if c not in indicator_df.columns]
    if missing:
        raise ValueError(f"Missing required indicator columns for macro factors: {missing}")

    factor_cfg = config["factors"]

    trend_scale = float(factor_cfg["trend_scale"])
    vol_scale = float(factor_cfg["vol_scale"])
    credit_scale = float(factor_cfg["credit_scale"])

    out = pd.DataFrame(index=indicator_df.index)

    out[Factors.MACRO_TREND_FACTOR] = (
        trend_scale * indicator_df[Indicators.SPY_TREND_Z]
    )

    out[Factors.MACRO_VOLATILITY_FACTOR] = (
        vol_scale * indicator_df[Indicators.VIX_Z]
    )

    out[Factors.MACRO_CREDIT_RISK_FACTOR] = (
        credit_scale * indicator_df[Indicators.HY_OAS_Z]
    )

    return out


def compute_macro_contexts(
    factor_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    """
    Build phase-1 macro contexts from macro factors.
    """
    required_cols = [
        Factors.MACRO_TREND_FACTOR,
        Factors.MACRO_VOLATILITY_FACTOR,
        Factors.MACRO_CREDIT_RISK_FACTOR,
    ]
    missing = [c for c in required_cols if c not in factor_df.columns]
    if missing:
        raise ValueError(f"Missing required factor columns for macro contexts: {missing}")

    context_cfg = config["contexts"]

    vol_weight = float(context_cfg["vol_weight"])
    credit_weight = float(context_cfg["credit_weight"])

    out = pd.DataFrame(index=factor_df.index)

    trend_factor = factor_df[Factors.MACRO_TREND_FACTOR]
    vol_factor = factor_df[Factors.MACRO_VOLATILITY_FACTOR]
    credit_factor = factor_df[Factors.MACRO_CREDIT_RISK_FACTOR]

    out[Contexts.MACRO_TREND_STRENGTH] = trend_factor

    out[Contexts.MACRO_RISK_PRESSURE] = (
        vol_weight * vol_factor.clip(lower=0.0)
        + credit_weight * credit_factor.clip(lower=0.0)
    )

    return out


def compute_macro_factor_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> FactorOutput:
    factor_df = compute_macro_factors(indicator_df, config)
    latest = factor_df.iloc[-1].dropna().to_dict()
    return FactorOutput(values={k: float(v) for k, v in latest.items()})


def compute_macro_context_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> ContextOutput:
    factor_df = compute_macro_factors(indicator_df, config)
    context_df = compute_macro_contexts(factor_df, config)
    latest = context_df.iloc[-1].dropna().to_dict()
    return ContextOutput(values={k: float(v) for k, v in latest.items()})