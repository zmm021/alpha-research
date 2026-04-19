from __future__ import annotations

from datetime import timedelta

import pandas as pd

from quant.common.enums import ActionSignal


# =========================
# Signal Stabilization Config
# =========================
ENABLE_COOLDOWN = True

# BUY 之后，短时间内不允许立刻 REDUCE / SELL
BUY_TO_EXIT_COOLDOWN = timedelta(hours=3)

# SELL / REDUCE 之后，短时间内不允许立刻 BUY
EXIT_TO_BUY_COOLDOWN = timedelta(hours=3)

# 若本次动作与上一次已发出的有效动作相同，则输出 HOLD
EMIT_ONLY_ON_SWITCH = True


# =========================
# Validation / Parsing
# =========================
def _validate_required_columns(feature_df: pd.DataFrame) -> None:
    required_cols = [
        "symbol_state",
        "sector_state_sector",
        "macro_state_macro",
        "symbol_range_position",
    ]
    missing = [c for c in required_cols if c not in feature_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for signal engine: {missing}")


def _parse_action(value: str) -> ActionSignal:
    try:
        return ActionSignal(value)
    except ValueError as exc:
        raise ValueError(f"Invalid action config value: {value}") from exc


def _normalize_state_value(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if hasattr(value, "value"):
        return str(value.value).lower()

    return str(value).lower()


def _safe_float(value, default: float = 0.5) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


# =========================
# State Family Helpers
# =========================
def _is_trend_state(symbol_state: str) -> bool:
    return symbol_state in {
        "trend_early",
        "trend_continuation",
        "trend_late",
        "trend_exhaustion",
        "pullback",
        "breakout_setup",
        "breakout",
        "breakout_failed",
    }


def _is_range_state(symbol_state: str) -> bool:
    return symbol_state in {
        "range_accumulation",
        "range_neutral",
        "range_distribution",
    }


def _is_risk_state(symbol_state: str) -> bool:
    return symbol_state in {
        "risk_rising",
        "risk_high",
        "breakdown_risk",
    }


# =========================
# Core Signal Logic by Regime
# =========================
def _trend_signal(
    symbol_state: str,
    sector_state: str,
    macro_state: str,
    signal_cfg: dict,
    default_action: ActionSignal,
) -> ActionSignal:
    allow_trend_buy = bool(signal_cfg.get("allow_trend_buy", True))
    allow_pullback_buy = bool(signal_cfg.get("allow_pullback_buy", True))
    allow_breakout_buy = bool(signal_cfg.get("allow_breakout_buy", True))

    breakout_requires_non_weak_sector = bool(
        signal_cfg.get("breakout_requires_non_weak_sector", True)
    )

    exhausted_action = _parse_action(signal_cfg.get("exhausted_action", "reduce"))

    macro_risk_off = macro_state == "risk_off"
    sector_weak = sector_state == "weak"

    if symbol_state == "trend_early":
        if macro_risk_off and sector_weak:
            return ActionSignal.HOLD
        return ActionSignal.BUY if allow_trend_buy else default_action

    if symbol_state == "trend_continuation":
        if macro_risk_off and sector_weak:
            return ActionSignal.REDUCE
        return ActionSignal.HOLD

    if symbol_state == "trend_late":
        if macro_risk_off and sector_weak:
            return ActionSignal.SELL
        if macro_risk_off or sector_weak:
            return ActionSignal.REDUCE
        return ActionSignal.REDUCE

    if symbol_state == "trend_exhaustion":
        return exhausted_action

    if symbol_state == "pullback":
        if macro_risk_off and sector_weak:
            return ActionSignal.HOLD
        return ActionSignal.BUY if allow_pullback_buy else default_action

    if symbol_state == "breakout_setup":
        if not allow_breakout_buy:
            return default_action
        if breakout_requires_non_weak_sector and sector_weak:
            return ActionSignal.HOLD
        if macro_risk_off:
            return ActionSignal.HOLD
        return ActionSignal.BUY

    if symbol_state == "breakout":
        if not allow_breakout_buy:
            return default_action
        if breakout_requires_non_weak_sector and sector_weak:
            return ActionSignal.HOLD
        if macro_risk_off and sector_weak:
            return ActionSignal.REDUCE
        return ActionSignal.BUY

    if symbol_state == "breakout_failed":
        return ActionSignal.SELL

    return default_action


def _range_signal(
    symbol_state: str,
    sector_state: str,
    macro_state: str,
    range_position: float,
    signal_cfg: dict,
    default_action: ActionSignal,
) -> ActionSignal:
    """
    区间逻辑（score版）：
    - 先根据 range_position 计算连续 score
    - 再把 score 映射成 buy / hold / reduce / sell
    """
    allow_range_buy = bool(signal_cfg.get("allow_range_buy", True))

    if pd.isna(range_position):
        return default_action

    # =========================================================
    # 1. range_position -> score
    #    0   = 区间底部   -> +1
    #    0.5 = 区间中部   -> 0
    #    1   = 区间顶部   -> -1
    # =========================================================
    score = (0.5 - float(range_position)) * 2.0

    # 可训练/可配置：score 放大系数
    range_score_scale = float(signal_cfg.get("range_score_scale", 1.0))
    score *= range_score_scale

    # =========================================================
    # 2. 宏观 / 板块环境削弱
    #    注意：这里只是削弱，不是硬切
    # =========================================================
    if macro_state == "risk_off":
        macro_range_penalty = float(signal_cfg.get("macro_range_penalty", 0.5))
        score *= macro_range_penalty

    if sector_state == "weak":
        sector_range_penalty = float(signal_cfg.get("sector_range_penalty", 0.7))
        score *= sector_range_penalty

    # =========================================================
    # 3. score -> signal
    # =========================================================
    buy_th = float(signal_cfg.get("range_buy_threshold", 0.6))
    reduce_th = float(signal_cfg.get("range_reduce_threshold", -0.3))
    sell_th = float(signal_cfg.get("range_sell_threshold", -0.6))

    if score >= buy_th:
        if macro_state == "risk_off" or sector_state == "weak":
            return ActionSignal.HOLD
        return ActionSignal.BUY if allow_range_buy else ActionSignal.HOLD

    if score <= sell_th:
        # 顶部极端弱化时，distribution 可以更激进
        if symbol_state == "range_distribution":
            range_distribution_action = _parse_action(
                signal_cfg.get("range_distribution_action", "sell")
            )
            return range_distribution_action

        range_upper_action = _parse_action(
            signal_cfg.get("range_upper_action", "sell")
        )
        return range_upper_action

    if score <= reduce_th:
        return ActionSignal.REDUCE

    return ActionSignal.HOLD


def _risk_signal(
    symbol_state: str,
    sector_state: str,
    macro_state: str,
    signal_cfg: dict,
    default_action: ActionSignal,
) -> ActionSignal:
    high_risk_action = _parse_action(signal_cfg.get("high_risk_action", "sell"))
    breakdown_action = _parse_action(signal_cfg.get("breakdown_action", "sell"))

    if symbol_state == "risk_rising":
        return ActionSignal.REDUCE

    if symbol_state == "risk_high":
        return high_risk_action

    if symbol_state == "breakdown_risk":
        return breakdown_action

    return default_action


# =========================
# Global Override Layer
# =========================
def _apply_global_overrides(
    current_signal: ActionSignal,
    symbol_state: str,
    sector_state: str,
    macro_state: str,
    signal_cfg: dict,
) -> ActionSignal:
    """
    全局修正：
    在极端环境下收缩风险，不直接替代 state-aware signal。
    """
    enable_risk_filter = bool(signal_cfg.get("enable_risk_filter", True))
    enable_sector_filter = bool(signal_cfg.get("enable_sector_filter", True))

    macro_risk_off = enable_risk_filter and macro_state == "risk_off"
    sector_weak = enable_sector_filter and sector_state == "weak"

    # 1. 双差环境
    if macro_risk_off and sector_weak:
        if symbol_state in {"risk_high", "breakdown_risk", "breakout_failed"}:
            return ActionSignal.SELL

        if symbol_state in {"trend_late", "trend_exhaustion", "range_distribution"}:
            return ActionSignal.SELL

        if symbol_state == "risk_rising":
            return ActionSignal.REDUCE

        if symbol_state in {
            "range_neutral",
            "range_accumulation",
            "trend_early",
            "pullback",
            "breakout_setup",
        }:
            return ActionSignal.AVOID

        if symbol_state == "trend_continuation":
            return ActionSignal.HOLD

        if current_signal == ActionSignal.BUY:
            return ActionSignal.AVOID

        return current_signal

    # 2. 只有 macro 差
    if macro_risk_off:
        if symbol_state in {"risk_high", "breakdown_risk", "breakout_failed"}:
            return ActionSignal.SELL

        if symbol_state in {"trend_late", "trend_exhaustion", "range_distribution"}:
            return ActionSignal.REDUCE

        if symbol_state == "risk_rising":
            return ActionSignal.REDUCE

        if _is_range_state(symbol_state) and current_signal == ActionSignal.BUY:
            return ActionSignal.HOLD

        if _is_trend_state(symbol_state) and current_signal == ActionSignal.BUY:
            return ActionSignal.HOLD

        return current_signal

    # 3. 只有 sector 差
    if sector_weak:
        if symbol_state in {"risk_high", "breakdown_risk", "breakout_failed"}:
            return ActionSignal.SELL

        if symbol_state in {"range_distribution", "risk_rising", "trend_late"}:
            return (
                ActionSignal.SELL
                if current_signal == ActionSignal.SELL
                else ActionSignal.REDUCE
            )

        if current_signal == ActionSignal.BUY and _is_range_state(symbol_state):
            return ActionSignal.HOLD

        if current_signal == ActionSignal.BUY and symbol_state in {
            "breakout",
            "breakout_setup",
        }:
            return ActionSignal.HOLD

        return current_signal

    return current_signal


# =========================
# Stabilization Layer
# =========================
def _apply_cooldown(
    current_signal: ActionSignal,
    last_action: ActionSignal | None,
    last_action_time,
    current_time,
) -> ActionSignal:
    """
    时间窗口 cooldown：
    - BUY 后，短时间内不允许 REDUCE / SELL
    - SELL / REDUCE 后，短时间内不允许 BUY
    """
    if not ENABLE_COOLDOWN:
        return current_signal

    if last_action is None or last_action_time is None:
        return current_signal

    time_diff = current_time - last_action_time

    if last_action == ActionSignal.BUY:
        if time_diff < BUY_TO_EXIT_COOLDOWN:
            if current_signal in {ActionSignal.REDUCE, ActionSignal.SELL}:
                return ActionSignal.HOLD

    if last_action in {ActionSignal.SELL, ActionSignal.REDUCE}:
        if time_diff < EXIT_TO_BUY_COOLDOWN:
            if current_signal == ActionSignal.BUY:
                return ActionSignal.HOLD

    return current_signal


def _collapse_repeated_signal(
    current_signal: ActionSignal,
    last_emitted_action: ActionSignal | None,
) -> ActionSignal:
    """
    如果没有动作切换，则默认 HOLD
    """
    if not EMIT_ONLY_ON_SWITCH:
        return current_signal

    if current_signal == ActionSignal.HOLD:
        return ActionSignal.HOLD

    if last_emitted_action is None:
        return current_signal

    if current_signal == last_emitted_action:
        return ActionSignal.HOLD

    return current_signal


# =========================
# Public API
# =========================
def compute_action_signals(
    feature_df: pd.DataFrame,
    config: dict,
) -> pd.Series:
    """
    Compute action signals from unified feature frame.

    Input:
        feature_df: feature_engine 输出
        config: signal config 或包含 signal 的 bundle

    Output:
        pd.Series[name="action_signal"]
    """
    _validate_required_columns(feature_df)

    print("\n=== symbol_state value counts ===")
    print(feature_df["symbol_state"].value_counts(dropna=False))

    print("\n=== sector_state_sector value counts ===")
    print(feature_df["sector_state_sector"].value_counts(dropna=False))

    print("\n=== macro_state_macro value counts ===")
    print(feature_df["macro_state_macro"].value_counts(dropna=False))

    signal_cfg = config.get("signal", config)
    default_action = _parse_action(signal_cfg.get("default_action", "hold"))

    macro_state_series = feature_df["macro_state_macro"]
    sector_state_series = feature_df["sector_state_sector"]
    symbol_state_series = feature_df["symbol_state"]
    range_position_series = feature_df["symbol_range_position"]

    signals: list[ActionSignal] = []

    # cooldown memory
    last_action_for_cooldown: ActionSignal | None = None
    last_action_time = None

    # emit memory
    last_emitted_action: ActionSignal | None = None

    for i in range(len(feature_df)):
        current_time = feature_df.index[i]

        macro_state = _normalize_state_value(macro_state_series.iloc[i])
        sector_state = _normalize_state_value(sector_state_series.iloc[i])
        symbol_state = _normalize_state_value(symbol_state_series.iloc[i])
        range_position = _safe_float(range_position_series.iloc[i], default=0.5)

        # 1. raw regime-aware signal
        if _is_trend_state(symbol_state):
            signal = _trend_signal(
                symbol_state=symbol_state,
                sector_state=sector_state,
                macro_state=macro_state,
                signal_cfg=signal_cfg,
                default_action=default_action,
            )

        elif _is_range_state(symbol_state):
            signal = _range_signal(
                symbol_state=symbol_state,
                sector_state=sector_state,
                macro_state=macro_state,
                range_position=range_position,
                signal_cfg=signal_cfg,
                default_action=default_action,
            )

        elif _is_risk_state(symbol_state):
            signal = _risk_signal(
                symbol_state=symbol_state,
                sector_state=sector_state,
                macro_state=macro_state,
                signal_cfg=signal_cfg,
                default_action=default_action,
            )

        else:
            signal = default_action

        # 2. global override
        signal = _apply_global_overrides(
            current_signal=signal,
            symbol_state=symbol_state,
            sector_state=sector_state,
            macro_state=macro_state,
            signal_cfg=signal_cfg,
        )

        # 3. cooldown stabilization
        signal = _apply_cooldown(
            current_signal=signal,
            last_action=last_action_for_cooldown,
            last_action_time=last_action_time,
            current_time=current_time,
        )

        # 4. if no switch, output HOLD
        signal = _collapse_repeated_signal(
            current_signal=signal,
            last_emitted_action=last_emitted_action,
        )

        # 5. update emit memory
        if signal in {
            ActionSignal.BUY,
            ActionSignal.SELL,
            ActionSignal.REDUCE,
            ActionSignal.AVOID,
        }:
            last_emitted_action = signal

        # 6. update cooldown memory
        if signal in {
            ActionSignal.BUY,
            ActionSignal.SELL,
            ActionSignal.REDUCE,
        }:
            last_action_for_cooldown = signal
            last_action_time = current_time

        signals.append(signal)

    return pd.Series(signals, index=feature_df.index, name="action_signal")