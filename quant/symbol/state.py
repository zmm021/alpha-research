from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts
from quant.common.enums import SymbolState
from quant.common.schemas import ContextOutput
from quant.common.types import ConfigDict


def _compute_single_symbol_state(
    trend_strength: float,
    volatility_state: float,
    position_quality: float,
    intraday_intent: float,
    exhaustion_risk: float,
    failure_risk: float,
    config: ConfigDict,
) -> SymbolState:
    state_cfg = config["state"]

    trend_threshold = float(state_cfg.get("trend_threshold", 0.3))
    range_threshold = float(state_cfg.get("range_threshold", 0.15))
    volatility_threshold = float(state_cfg.get("volatility_threshold", 0.05))
    risk_vol_threshold = float(state_cfg.get("risk_vol_threshold", 0.10))
    exhaustion_threshold = float(state_cfg.get("exhaustion_threshold", 0.8))
    failure_threshold = float(state_cfg.get("failure_threshold", 0.8))
    breakout_intent_threshold = float(state_cfg.get("breakout_intent_threshold", 0.02))
    pullback_position_threshold = float(state_cfg.get("pullback_position_threshold", 0.02))

    # 1. High risk first
    if volatility_state >= risk_vol_threshold and failure_risk >= failure_threshold:
        return SymbolState.HIGH_RISK

    # 2. Breakdown risk
    if failure_risk >= failure_threshold:
        return SymbolState.BREAKDOWN_RISK

    # 3. Exhaustion
    if exhaustion_risk >= exhaustion_threshold:
        return SymbolState.EXHAUSTED

    # 4. Breakout setup
    if (
        abs(trend_strength) >= trend_threshold
        and intraday_intent >= breakout_intent_threshold
        and volatility_state < risk_vol_threshold
    ):
        return SymbolState.BREAKOUT_SETUP

    # 5. Trend / pullback
    if trend_strength >= trend_threshold:
        if position_quality <= pullback_position_threshold:
            return SymbolState.PULLBACK
        return SymbolState.TREND

    # 6. Range fallback
    if abs(trend_strength) <= range_threshold and volatility_state <= volatility_threshold:
        return SymbolState.RANGE

    return SymbolState.RANGE


def compute_symbol_states(
    context_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    required_cols = [
        Contexts.SYMBOL_TREND_STRENGTH,
        Contexts.SYMBOL_VOLATILITY_STATE,
        Contexts.SYMBOL_POSITION_QUALITY,
        Contexts.SYMBOL_INTRADAY_INTENT,
        Contexts.SYMBOL_EXHAUSTION_RISK,
        Contexts.SYMBOL_FAILURE_RISK,
    ]
    missing = [c for c in required_cols if c not in context_df.columns]
    if missing:
        raise ValueError(f"Missing required context columns for symbol state: {missing}")

    return context_df.apply(
        lambda row: _compute_single_symbol_state(
            trend_strength=float(row[Contexts.SYMBOL_TREND_STRENGTH]),
            volatility_state=float(row[Contexts.SYMBOL_VOLATILITY_STATE]),
            position_quality=float(row[Contexts.SYMBOL_POSITION_QUALITY]),
            intraday_intent=float(row[Contexts.SYMBOL_INTRADAY_INTENT]),
            exhaustion_risk=float(row[Contexts.SYMBOL_EXHAUSTION_RISK]),
            failure_risk=float(row[Contexts.SYMBOL_FAILURE_RISK]),
            config=config,
        ),
        axis=1,
    )


def compute_symbol_state_output(
    context_output: ContextOutput,
    config: ConfigDict,
) -> SymbolState:
    values = context_output.values

    return _compute_single_symbol_state(
        trend_strength=float(values.get(Contexts.SYMBOL_TREND_STRENGTH, 0.0)),
        volatility_state=float(values.get(Contexts.SYMBOL_VOLATILITY_STATE, 0.0)),
        position_quality=float(values.get(Contexts.SYMBOL_POSITION_QUALITY, 0.0)),
        intraday_intent=float(values.get(Contexts.SYMBOL_INTRADAY_INTENT, 0.0)),
        exhaustion_risk=float(values.get(Contexts.SYMBOL_EXHAUSTION_RISK, 0.0)),
        failure_risk=float(values.get(Contexts.SYMBOL_FAILURE_RISK, 0.0)),
        config=config,
    )