from __future__ import annotations

import pandas as pd

from quant.common.constants import Contexts
from quant.common.enums import SymbolState
from quant.common.schemas import ContextOutput
from quant.common.types import ConfigDict


def _compute_single_symbol_state(
    trend_strength: float,
    trend_slope: float,
    reversal_pressure: float,
    volatility_state: float,
    position_quality: float,
    intraday_intent: float,
    exhaustion_risk: float,
    failure_risk: float,
    config: ConfigDict,
) -> SymbolState:
    state_cfg = config["state"]

    # ===== thresholds =====
    trend_threshold = float(state_cfg.get("trend_threshold", 0.30))
    strong_trend_threshold = float(state_cfg.get("strong_trend_threshold", 0.60))
    weak_trend_threshold = float(state_cfg.get("weak_trend_threshold", 0.20))

    range_threshold = float(state_cfg.get("range_threshold", 0.15))
    volatility_threshold = float(state_cfg.get("volatility_threshold", 0.05))
    risk_vol_threshold = float(state_cfg.get("risk_vol_threshold", 0.08))

    exhaustion_threshold = float(state_cfg.get("exhaustion_threshold", 0.55))
    late_trend_exhaustion_threshold = float(
        state_cfg.get("late_trend_exhaustion_threshold", 0.35)
    )

    failure_threshold = float(state_cfg.get("failure_threshold", 0.50))
    rising_risk_threshold = float(state_cfg.get("rising_risk_threshold", 0.30))

    breakout_intent_threshold = float(state_cfg.get("breakout_intent_threshold", 0.02))
    confirmed_breakout_intent_threshold = float(
        state_cfg.get("confirmed_breakout_intent_threshold", 0.05)
    )
    breakout_failure_threshold = float(
        state_cfg.get("breakout_failure_threshold", 0.40)
    )

    pullback_position_threshold = float(
        state_cfg.get("pullback_position_threshold", 0.10)
    )
    accumulation_position_threshold = float(
        state_cfg.get("accumulation_position_threshold", 0.35)
    )
    distribution_position_threshold = float(
        state_cfg.get("distribution_position_threshold", 0.65)
    )

    reversal_pressure_threshold = float(
        state_cfg.get("reversal_pressure_threshold", 0.30)
    )
    strong_reversal_pressure_threshold = float(
        state_cfg.get("strong_reversal_pressure_threshold", 0.50)
    )

    # ------------------------------------------------------------------
    # 1) Hard risk first
    # ------------------------------------------------------------------
    if (
        volatility_state >= risk_vol_threshold
        and failure_risk >= failure_threshold
    ):
        return SymbolState.RISK_HIGH

    if failure_risk >= failure_threshold:
        return SymbolState.BREAKDOWN_RISK

    # ------------------------------------------------------------------
    # 2) Failed breakout / reversal transition
    # ------------------------------------------------------------------
    # breakout intent exists, but price intent/slope already turns against it
    if (
        intraday_intent >= breakout_intent_threshold
        and (
            failure_risk >= breakout_failure_threshold
            or reversal_pressure >= strong_reversal_pressure_threshold
            or (trend_slope < 0 and reversal_pressure >= reversal_pressure_threshold)
        )
        and trend_strength >= weak_trend_threshold
    ):
        return SymbolState.BREAKOUT_FAILED

    # ------------------------------------------------------------------
    # 3) Trend exhaustion first
    # ------------------------------------------------------------------
    if exhaustion_risk >= exhaustion_threshold:
        return SymbolState.TREND_EXHAUSTION

    # ------------------------------------------------------------------
    # 4) Confirmed breakout
    # ------------------------------------------------------------------
    if (
        trend_strength >= trend_threshold
        and intraday_intent >= confirmed_breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
        and trend_slope >= 0
        and exhaustion_risk < exhaustion_threshold
    ):
        return SymbolState.BREAKOUT

    # ------------------------------------------------------------------
    # 5) Breakout setup
    # ------------------------------------------------------------------
    if (
        trend_strength >= trend_threshold
        and intraday_intent >= breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
        and exhaustion_risk < exhaustion_threshold
    ):
        return SymbolState.BREAKOUT_SETUP

    # ------------------------------------------------------------------
    # 6) Trend lifecycle
    # ------------------------------------------------------------------
    if trend_strength >= strong_trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
            or trend_slope < 0
        ):
            return SymbolState.TREND_LATE
        return SymbolState.TREND_CONTINUATION

    if trend_strength >= trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
            or trend_slope < 0
        ):
            return SymbolState.TREND_LATE
        return SymbolState.TREND_EARLY

    # ------------------------------------------------------------------
    # 7) Pullback
    # keep this after breakout/trend so it doesn't swallow too much
    # ------------------------------------------------------------------
    if (
        trend_strength >= weak_trend_threshold
        and position_quality <= pullback_position_threshold
        and intraday_intent <= breakout_intent_threshold
        and failure_risk < rising_risk_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolState.PULLBACK

    # ------------------------------------------------------------------
    # 8) Range lifecycle
    # ------------------------------------------------------------------
    in_range = (
        abs(trend_strength) <= range_threshold
        and volatility_state <= volatility_threshold
    )

    if in_range:
        if position_quality <= accumulation_position_threshold:
            return SymbolState.RANGE_ACCUMULATION

        if position_quality >= distribution_position_threshold:
            return SymbolState.RANGE_DISTRIBUTION

        return SymbolState.RANGE_NEUTRAL

    # ------------------------------------------------------------------
    # 9) Soft risk / weakening / transition
    # ------------------------------------------------------------------
    if (
        failure_risk >= rising_risk_threshold
        or volatility_state >= risk_vol_threshold
        or reversal_pressure >= reversal_pressure_threshold
        or (trend_slope < 0 and reversal_pressure >= reversal_pressure_threshold)
    ):
        return SymbolState.RISK_RISING

    # ------------------------------------------------------------------
    # 10) Fallback
    # ------------------------------------------------------------------
    return SymbolState.RANGE_NEUTRAL


def compute_symbol_states(
    context_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    required_cols = [
        Contexts.SYMBOL_TREND_STRENGTH,
        Contexts.SYMBOL_TREND_SLOPE,
        Contexts.SYMBOL_REVERSAL_PRESSURE,
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
            trend_slope=float(row[Contexts.SYMBOL_TREND_SLOPE]),
            reversal_pressure=float(row[Contexts.SYMBOL_REVERSAL_PRESSURE]),
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
        trend_slope=float(values.get(Contexts.SYMBOL_TREND_SLOPE, 0.0)),
        reversal_pressure=float(values.get(Contexts.SYMBOL_REVERSAL_PRESSURE, 0.0)),
        volatility_state=float(values.get(Contexts.SYMBOL_VOLATILITY_STATE, 0.0)),
        position_quality=float(values.get(Contexts.SYMBOL_POSITION_QUALITY, 0.0)),
        intraday_intent=float(values.get(Contexts.SYMBOL_INTRADAY_INTENT, 0.0)),
        exhaustion_risk=float(values.get(Contexts.SYMBOL_EXHAUSTION_RISK, 0.0)),
        failure_risk=float(values.get(Contexts.SYMBOL_FAILURE_RISK, 0.0)),
        config=config,
    )