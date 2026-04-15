from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts, Factors, Indicators
from quant.common.schemas import ContextOutput, FactorOutput
from quant.common.types import ConfigDict


# =========================
# Helpers
# =========================

def _safe_sign(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))


# =========================
# Core
# =========================

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
    ]
    missing = [c for c in required_cols if c not in indicator_df.columns]
    if missing:
        raise ValueError(f"Missing required indicator columns for symbol factors: {missing}")

    factor_cfg = config["factors"]

    trend_scale = float(factor_cfg["trend_scale"])
    volatility_scale = float(factor_cfg["volatility_scale"])
    liquidity_scale = float(factor_cfg["liquidity_scale"])
    position_scale = float(factor_cfg["position_scale"])
    intraday_scale = float(factor_cfg["intraday_scale"])

    trend_cross_weight = float(factor_cfg["trend_cross_weight"])
    trend_slope_weight = float(factor_cfg["trend_slope_weight"])

    intraday_gap_weight = float(factor_cfg["intraday_gap_weight"])
    intraday_vwap_weight = float(factor_cfg["intraday_vwap_weight"])

    out = pd.DataFrame(index=indicator_df.index)

    ma20 = indicator_df[Indicators.MA20]
    ma50 = indicator_df[Indicators.MA50]
    ma20_slope = indicator_df[Indicators.MA20_SLOPE]

    atr_pct = indicator_df[Indicators.ATR_PCT]
    volume_ratio = indicator_df[Indicators.VOLUME_RATIO]
    distance_to_high = indicator_df[Indicators.DISTANCE_TO_HIGH]
    gap_pct = indicator_df[Indicators.GAP_PCT]
    price_vs_vwap = indicator_df[Indicators.PRICE_VS_VWAP]

    # ===== Trend factor =====
    ma_cross_signal = (ma20 > ma50).astype(float) * 2.0 - 1.0
    slope_direction = _safe_sign(ma20_slope.fillna(0.0))

    out[Factors.SYMBOL_TREND_FACTOR] = trend_scale * (
        trend_cross_weight * ma_cross_signal
        + trend_slope_weight * slope_direction
    )

    # ===== Volatility factor =====
    out[Factors.SYMBOL_VOLATILITY_FACTOR] = volatility_scale * atr_pct

    # ===== Liquidity factor =====
    out[Factors.SYMBOL_LIQUIDITY_FACTOR] = liquidity_scale * volume_ratio

    # ===== Position factor =====
    out[Factors.SYMBOL_POSITION_FACTOR] = position_scale * (-distance_to_high)

    # ===== Intraday intent factor =====
    out[Factors.SYMBOL_INTRADAY_INTENT_FACTOR] = intraday_scale * (
        intraday_gap_weight * gap_pct
        + intraday_vwap_weight * price_vs_vwap
    )

    return out


def compute_symbol_contexts(
    factor_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    required_cols = [
        Factors.SYMBOL_TREND_FACTOR,
        Factors.SYMBOL_VOLATILITY_FACTOR,
        Factors.SYMBOL_LIQUIDITY_FACTOR,
        Factors.SYMBOL_POSITION_FACTOR,
        Factors.SYMBOL_INTRADAY_INTENT_FACTOR,
    ]
    missing = [c for c in required_cols if c not in factor_df.columns]
    if missing:
        raise ValueError(f"Missing required factor columns for symbol contexts: {missing}")

    context_cfg = config["contexts"]

    exhaustion_position_weight = float(context_cfg["exhaustion_position_weight"])
    exhaustion_intraday_weight = float(context_cfg["exhaustion_intraday_weight"])

    failure_vol_weight = float(context_cfg["failure_vol_weight"])
    failure_intraday_weight = float(context_cfg["failure_intraday_weight"])

    out = pd.DataFrame(index=factor_df.index)

    trend_factor = factor_df[Factors.SYMBOL_TREND_FACTOR]
    volatility_factor = factor_df[Factors.SYMBOL_VOLATILITY_FACTOR]
    liquidity_factor = factor_df[Factors.SYMBOL_LIQUIDITY_FACTOR]
    position_factor = factor_df[Factors.SYMBOL_POSITION_FACTOR]
    intraday_factor = factor_df[Factors.SYMBOL_INTRADAY_INTENT_FACTOR]

    out[Contexts.SYMBOL_TREND_STRENGTH] = trend_factor
    out[Contexts.SYMBOL_VOLATILITY_STATE] = volatility_factor
    out[Contexts.SYMBOL_POSITION_QUALITY] = position_factor
    out[Contexts.SYMBOL_INTRADAY_INTENT] = intraday_factor
    out[Contexts.SYMBOL_LIQUIDITY_QUALITY] = liquidity_factor

    # close to highs + strong push => exhaustion risk
    out[Contexts.SYMBOL_EXHAUSTION_RISK] = (
        exhaustion_position_weight * position_factor.clip(lower=0.0)
        + exhaustion_intraday_weight * intraday_factor.clip(lower=0.0)
    )

    # high vol + negative intraday intent => failure risk
    out[Contexts.SYMBOL_FAILURE_RISK] = (
        failure_vol_weight * volatility_factor.clip(lower=0.0)
        + failure_intraday_weight * (-intraday_factor).clip(lower=0.0)
    )

    return out


def compute_symbol_factor_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> FactorOutput:
    factor_df = compute_symbol_factors(indicator_df, config)
    latest = factor_df.iloc[-1].dropna().to_dict()
    return FactorOutput(values={k: float(v) for k, v in latest.items()})


def compute_symbol_context_output(
    indicator_df: pd.DataFrame,
    config: ConfigDict,
) -> ContextOutput:
    factor_df = compute_symbol_factors(indicator_df, config)
    context_df = compute_symbol_contexts(factor_df, config)
    latest = context_df.iloc[-1].dropna().to_dict()
    return ContextOutput(values={k: float(v) for k, v in latest.items()})