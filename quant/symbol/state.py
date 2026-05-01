from __future__ import annotations

import pandas as pd

from quant.common.constants import StructureScores
from quant.common.enums import SymbolState
from quant.common.schemas import StructureOutput
from quant.common.types import ConfigDict


def _compute_single_symbol_state(
    trend_strength: float,
    trend_slope: float,
    volatility_state: float,
    position_quality: float,
    range_position: float,
    intraday_intent: float,
    exhaustion_risk: float,
    failure_risk: float,
    reversal_pressure: float,
    config: ConfigDict,
) -> SymbolState:
    state_cfg = config["state"]

    # =========================
    # Base thresholds
    # =========================
    trend_threshold = float(state_cfg.get("trend_threshold", 0.30))
    strong_trend_threshold = float(state_cfg.get("strong_trend_threshold", 0.60))
    weak_trend_threshold = float(state_cfg.get("weak_trend_threshold", 0.20))

    range_threshold = float(state_cfg.get("range_threshold", 0.15))
    volatility_threshold = float(state_cfg.get("volatility_threshold", 0.05))
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
    breakout_failure_threshold = float(
        state_cfg.get("breakout_failure_threshold", 0.70)
    )

    pullback_position_threshold = float(
        state_cfg.get("pullback_position_threshold", 0.02)
    )

    # 原来 accumulation/distribution 阈值你已有，沿用
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

    # 新增但可缺省
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

    # clip 防御
    range_position = min(max(range_position, 0.0), 1.0)

    # =========================
    # 1. Hard risk states first
    # =========================
    if (
        failure_risk >= failure_threshold
        and reversal_pressure >= strong_reversal_pressure_threshold
        and volatility_state >= risk_vol_threshold
    ):
        return SymbolState.RISK_HIGH

    if (
        failure_risk >= failure_threshold
        and reversal_pressure >= reversal_pressure_threshold
    ):
        return SymbolState.BREAKDOWN_RISK

    # =========================
    # 2. Decide whether this bar is structurally range-like
    #    range should be a primary regime, not fallback
    # =========================
    in_range_base = (
        abs(trend_strength) <= range_threshold
        and volatility_state <= risk_vol_threshold
        and abs(trend_slope) <= range_slope_abs_threshold
        and failure_risk < failure_threshold
    )

    if in_range_base:
        if range_position <= range_buy_position_threshold:
            return SymbolState.RANGE_ACCUMULATION

        if range_position >= range_sell_position_threshold:
            return SymbolState.RANGE_DISTRIBUTION

        return SymbolState.RANGE_NEUTRAL

    # =========================
    # 3. Breakout / failed breakout
    #    only valid near upper bound with real intent
    # =========================
    if (
        range_position >= breakout_range_position_threshold
        and trend_strength >= weak_trend_threshold
        and intraday_intent >= confirmed_breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolState.BREAKOUT

    if (
        range_position >= breakout_setup_range_position_threshold
        and trend_strength >= weak_trend_threshold
        and intraday_intent >= breakout_intent_threshold
        and failure_risk < breakout_failure_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolState.BREAKOUT_SETUP

    if (
        range_position >= breakout_setup_range_position_threshold
        and intraday_intent >= breakout_intent_threshold
        and failure_risk >= breakout_failure_threshold
    ):
        return SymbolState.BREAKOUT_FAILED

    # =========================
    # 4. Pullback inside trend
    #    用 range_position 辅助，不再只看 position_quality
    # =========================
    if (
        trend_strength >= trend_threshold
        and range_position <= range_buy_position_threshold
        and failure_risk < rising_risk_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolState.PULLBACK

    # 兼容你原有的 position_quality 判断
    if (
        trend_strength >= trend_threshold
        and position_quality <= pullback_position_threshold
        and failure_risk < rising_risk_threshold
        and reversal_pressure < reversal_pressure_threshold
    ):
        return SymbolState.PULLBACK

    # =========================
    # 5. Trend lifecycle
    # =========================
    if trend_strength >= strong_trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
        ):
            return SymbolState.TREND_LATE
        return SymbolState.TREND_CONTINUATION

    if trend_strength >= trend_threshold:
        if (
            exhaustion_risk >= late_trend_exhaustion_threshold
            or reversal_pressure >= reversal_pressure_threshold
        ):
            return SymbolState.TREND_LATE
        return SymbolState.TREND_EARLY

    if exhaustion_risk >= exhaustion_threshold:
        return SymbolState.TREND_EXHAUSTION

    # =========================
    # 6. Residual risk state
    # =========================
    if (
        failure_risk >= rising_risk_threshold
        or reversal_pressure >= reversal_pressure_threshold
        or volatility_state >= risk_vol_threshold
    ):
        return SymbolState.RISK_RISING

    # =========================
    # 7. Fallback
    # =========================
    if range_position <= accumulation_position_threshold:
        return SymbolState.RANGE_ACCUMULATION

    if range_position >= distribution_position_threshold:
        return SymbolState.RANGE_DISTRIBUTION

    return SymbolState.RANGE_NEUTRAL


def compute_symbol_states(
    structure_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    required_cols = [
        StructureScores.SYMBOL_TREND_STRENGTH,
        StructureScores.SYMBOL_TREND_SLOPE,
        StructureScores.SYMBOL_VOLATILITY_STATE,
        StructureScores.SYMBOL_POSITION_QUALITY,
        StructureScores.SYMBOL_RANGE_POSITION,
        StructureScores.SYMBOL_INTRADAY_INTENT,
        StructureScores.SYMBOL_EXHAUSTION_RISK,
        StructureScores.SYMBOL_FAILURE_RISK,
        StructureScores.SYMBOL_REVERSAL_PRESSURE,
    ]
    missing = [c for c in required_cols if c not in structure_df.columns]
    if missing:
        raise ValueError(f"Missing required context columns for symbol state: {missing}")

    return structure_df.apply(
        lambda row: _compute_single_symbol_state(
            trend_strength=float(row[StructureScores.SYMBOL_TREND_STRENGTH]),
            trend_slope=float(row[StructureScores.SYMBOL_TREND_SLOPE]),
            volatility_state=float(row[StructureScores.SYMBOL_VOLATILITY_STATE]),
            position_quality=float(row[StructureScores.SYMBOL_POSITION_QUALITY]),
            range_position=float(row[StructureScores.SYMBOL_RANGE_POSITION]),
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
) -> SymbolState:
    values = structure_output.values

    return _compute_single_symbol_state(
        trend_strength=float(values.get(StructureScores.SYMBOL_TREND_STRENGTH, 0.0)),
        trend_slope=float(values.get(StructureScores.SYMBOL_TREND_SLOPE, 0.0)),
        volatility_state=float(values.get(StructureScores.SYMBOL_VOLATILITY_STATE, 0.0)),
        position_quality=float(values.get(StructureScores.SYMBOL_POSITION_QUALITY, 0.0)),
        range_position=float(values.get(StructureScores.SYMBOL_RANGE_POSITION, 0.5)),
        intraday_intent=float(values.get(StructureScores.SYMBOL_INTRADAY_INTENT, 0.0)),
        exhaustion_risk=float(values.get(StructureScores.SYMBOL_EXHAUSTION_RISK, 0.0)),
        failure_risk=float(values.get(StructureScores.SYMBOL_FAILURE_RISK, 0.0)),
        reversal_pressure=float(values.get(StructureScores.SYMBOL_REVERSAL_PRESSURE, 0.0)),
        config=config,
    )