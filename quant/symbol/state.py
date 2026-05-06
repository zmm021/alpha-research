from __future__ import annotations

import pandas as pd

from quant.common.constants import StructureScores
from quant.common.enums import SymbolStructureState, SymbolLiquidityState
from quant.common.schemas import StructureOutput
from quant.common.types import ConfigDict


def _compute_single_symbol_state(
    trend_strength: float,
    trend_slope: float,
    volatility_state: float,
    position_quality_short: float,
    position_quality_mid: float,
    range_position_short: float,
    range_position_mid: float,
    intraday_intent: float,
    exhaustion_risk: float,
    failure_risk: float,
    reversal_pressure: float,
    config: ConfigDict,
) -> SymbolStructureState:
    state_cfg = config["state"]

    trend_threshold = float(state_cfg.get("trend_threshold", 0.30))
    strong_trend_threshold = float(state_cfg.get("strong_trend_threshold", 0.60))
    weak_trend_threshold = float(state_cfg.get("weak_trend_threshold", 0.20))

    range_threshold = float(state_cfg.get("range_threshold", 0.15))
    risk_vol_threshold = float(state_cfg.get("risk_vol_threshold", 0.10))

    exhaustion_threshold = float(state_cfg.get("exhaustion_threshold", 0.80))
    late_trend_exhaustion_threshold = float(
        state_cfg.get("late_trend_exhaustion_threshold", 0.60)
    )

    failure_threshold = float(state_cfg.get("failure_threshold", 0.80))
    rising_risk_threshold = float(state_cfg.get("rising_risk_threshold", 0.55))

    breakout_intent_threshold = float(state_cfg.get("breakout_intent_threshold", 0.02))
    confirmed_breakout_intent_threshold = float(
        state_cfg.get("confirmed_breakout_intent_threshold", 0.05)
    )
    breakout_failure_threshold = float(state_cfg.get("breakout_failure_threshold", 0.70))

    pullback_position_threshold = float(
        state_cfg.get("pullback_position_threshold", 0.02)
    )

    accumulation_position_threshold = float(
        state_cfg.get("accumulation_position_threshold", 0.35)
    )
    distribution_position_threshold = float(
        state_cfg.get("distribution_position_threshold", 0.65)
    )

    reversal_pressure_threshold = float(
        state_cfg.get("reversal_pressure_threshold", 0.45)
    )
    strong_reversal_pressure_threshold = float(
        state_cfg.get("strong_reversal_pressure_threshold", 0.60)
    )

    range_buy_position_threshold = float(
        state_cfg.get("range_buy_position_threshold", 0.30)
    )
    range_sell_position_threshold = float(
        state_cfg.get("range_sell_position_threshold", 0.70)
    )
    breakout_range_position_threshold = float(
        state_cfg.get("breakout_range_position_threshold", 0.85)
    )
    breakout_setup_range_position_threshold = float(
        state_cfg.get("breakout_setup_range_position_threshold", 0.75)
    )
    range_slope_abs_threshold = float(
        state_cfg.get("range_slope_abs_threshold", 0.50)
    )

    range_position_short = min(max(range_position_short, 0.0), 1.0)
    range_position_mid = min(max(range_position_mid, 0.0), 1.0)

    # 1. Hard risk states first
    if (
        failure_risk >= failure_threshold
        and reversal_pressure >= strong_reversal_pressure_threshold
        and volatility_state >= risk_vol_threshold
    ):
        return SymbolStructureState.RISK_HIGH

    if (
        failure_risk >= failure_threshold
        and reversal_pressure >= reversal_pressure_threshold
    ):
        return SymbolStructureState.BREAKDOWN_RISK

    # 2. Range-like state uses short position
    in_range_base = (
        abs(trend_strength) <= range_threshold
        and volatility_state <= risk_vol_threshold
        and abs(trend_slope) <= range_slope_abs_threshold
        and failure_risk < failure_threshold
    )

    if in_range_base:
        if range_position_short <= range_buy_position_threshold:
            return SymbolStructureState.RANGE_ACCUMULATION

        if range_position_short >= range_sell_position_threshold:
            return SymbolStructureState.RANGE_DISTRIBUTION

        return SymbolStructureState.RANGE_NEUTRAL

    # 3. Breakout uses mid position
    if (
        range_position_mid >= breakout_range_position_threshold
        and trend_strength >= weak_trend_threshold
        and intraday_intent >= confirmed_breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolStructureState.BREAKOUT

    if (
        range_position_mid >= breakout_setup_range_position_threshold
        and trend_strength >= weak_trend_threshold
        and intraday_intent >= breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolStructureState.BREAKOUT_SETUP

    if (
        range_position_mid >= breakout_setup_range_position_threshold
        and intraday_intent >= breakout_intent_threshold
        and failure_risk >= breakout_failure_threshold
    ):
        return SymbolStructureState.BREAKOUT_FAILED

    # 4. Pullback inside trend uses mid position
    if (
        trend_strength >= trend_threshold
        and range_position_mid <= range_buy_position_threshold
        and failure_risk < rising_risk_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolStructureState.PULLBACK

    if (
        trend_strength >= trend_threshold
        and position_quality_mid <= pullback_position_threshold
        and failure_risk < rising_risk_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolStructureState.PULLBACK

    # 5. Trend lifecycle
    if trend_strength >= strong_trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
        ):
            return SymbolStructureState.TREND_LATE
        return SymbolStructureState.TREND_CONTINUATION

    if trend_strength >= trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
        ):
            return SymbolStructureState.TREND_LATE
        return SymbolStructureState.TREND_EARLY

    if exhaustion_risk >= exhaustion_threshold:
        return SymbolStructureState.TREND_EXHAUSTION

    # 6. Residual risk state
    if (
        failure_risk >= rising_risk_threshold
        or reversal_pressure >= reversal_pressure_threshold
        or volatility_state >= risk_vol_threshold
    ):
        return SymbolStructureState.RISK_RISING

    # 7. Fallback uses short position
    if range_position_short <= accumulation_position_threshold:
        return SymbolStructureState.RANGE_ACCUMULATION

    if range_position_short >= distribution_position_threshold:
        return SymbolStructureState.RANGE_DISTRIBUTION

    return SymbolStructureState.RANGE_NEUTRAL


def compute_symbol_states(
    structure_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    required_cols = [
        StructureScores.SYMBOL_TREND_STRENGTH,
        StructureScores.SYMBOL_TREND_SLOPE,
        StructureScores.SYMBOL_VOLATILITY_STATE,
        StructureScores.SYMBOL_POSITION_QUALITY_SHORT,
        StructureScores.SYMBOL_POSITION_QUALITY_MID,
        StructureScores.SYMBOL_RANGE_POSITION_SHORT,
        StructureScores.SYMBOL_RANGE_POSITION_MID,
        StructureScores.SYMBOL_INTRADAY_INTENT,
        StructureScores.SYMBOL_EXHAUSTION_RISK,
        StructureScores.SYMBOL_FAILURE_RISK,
        StructureScores.SYMBOL_REVERSAL_PRESSURE,
    ]
    missing = [c for c in required_cols if c not in structure_df.columns]
    if missing:
        raise ValueError(f"Missing required structure score columns for symbol state: {missing}")

    return structure_df.apply(
        lambda row: _compute_single_symbol_state(
            trend_strength=float(row[StructureScores.SYMBOL_TREND_STRENGTH]),
            trend_slope=float(row[StructureScores.SYMBOL_TREND_SLOPE]),
            volatility_state=float(row[StructureScores.SYMBOL_VOLATILITY_STATE]),
            position_quality_short=float(row[StructureScores.SYMBOL_POSITION_QUALITY_SHORT]),
            position_quality_mid=float(row[StructureScores.SYMBOL_POSITION_QUALITY_MID]),
            range_position_short=float(row[StructureScores.SYMBOL_RANGE_POSITION_SHORT]),
            range_position_mid=float(row[StructureScores.SYMBOL_RANGE_POSITION_MID]),
            intraday_intent=float(row[StructureScores.SYMBOL_INTRADAY_INTENT]),
            exhaustion_risk=float(row[StructureScores.SYMBOL_EXHAUSTION_RISK]),
            failure_risk=float(row[StructureScores.SYMBOL_FAILURE_RISK]),
            reversal_pressure=float(row[StructureScores.SYMBOL_REVERSAL_PRESSURE]),
            config=config,
        ),
        axis=1,
    )


def compute_symbol_state_output(
    structure_output: StructureOutput,
    config: ConfigDict,
) -> SymbolStructureState:
    values = structure_output.values

    return _compute_single_symbol_state(
        trend_strength=float(values.get(StructureScores.SYMBOL_TREND_STRENGTH, 0.0)),
        trend_slope=float(values.get(StructureScores.SYMBOL_TREND_SLOPE, 0.0)),
        volatility_state=float(values.get(StructureScores.SYMBOL_VOLATILITY_STATE, 0.0)),
        position_quality_short=float(values.get(StructureScores.SYMBOL_POSITION_QUALITY_SHORT, 0.0)),
        position_quality_mid=float(values.get(StructureScores.SYMBOL_POSITION_QUALITY_MID, 0.0)),
        range_position_short=float(values.get(StructureScores.SYMBOL_RANGE_POSITION_SHORT, 0.5)),
        range_position_mid=float(values.get(StructureScores.SYMBOL_RANGE_POSITION_MID, 0.5)),
        intraday_intent=float(values.get(StructureScores.SYMBOL_INTRADAY_INTENT, 0.0)),
        exhaustion_risk=float(values.get(StructureScores.SYMBOL_EXHAUSTION_RISK, 0.0)),
        failure_risk=float(values.get(StructureScores.SYMBOL_FAILURE_RISK, 0.0)),
        reversal_pressure=float(values.get(StructureScores.SYMBOL_REVERSAL_PRESSURE, 0.0)),
        config=config,
    )

def compute_symbol_liquidity_state(
    liquidity_quality: float,
) -> SymbolLiquidityState:
    if liquidity_quality <= -0.5:
        return SymbolLiquidityState.DRY

    if liquidity_quality <= 0.0:
        return SymbolLiquidityState.THIN

    if liquidity_quality >= 0.5:
        return SymbolLiquidityState.LIQUID

    return SymbolLiquidityState.NORMAL

def compute_symbol_liquidity_state_output(
    structure_output: StructureOutput,
    config: ConfigDict | None = None,
) -> SymbolLiquidityState:
    values = structure_output.values

    liquidity_quality = float(
        values.get(StructureScores.SYMBOL_LIQUIDITY_QUALITY, 0.0)
    )

    return compute_symbol_liquidity_state(
        liquidity_quality=liquidity_quality,
    )