from __future__ import annotations

from datetime import timedelta

import pandas as pd

from quant.common.enums import ActionSignal


# =========================
# Basic Position Config
# =========================
INITIAL_POSITION = 0

ENTRY_SIZE = 200
ADD_SIZE = 200
REDUCE_SIZE = 200
SELL_SIZE = 200

MIN_POSITION = 0
MAX_POSITION = 1000

# SELL 是否一次性清仓
SELL_ALL_ON_SELL = False

# 是否只允许从空仓开仓，不允许中途继续加仓
ENTRY_ONLY_WHEN_FLAT = False


# =========================
# Execution Cooldown Config
# =========================
ENABLE_POSITION_COOLDOWN = True

BUY_COOLDOWN = timedelta(hours=3)
EXIT_COOLDOWN = timedelta(hours=3)


# =========================
# Execution Price Gap Config
# =========================
ENABLE_PRICE_GAP = True

# 相对于上一次 BUY 成交价，至少偏离多少才允许下一次 BUY
BUY_PRICE_GAP_PCT = 0.02

# 相对于上一次 REDUCE / SELL 成交价，至少偏离多少才允许下一次 REDUCE
REDUCE_PRICE_GAP_PCT = 0.02

# 相对于上一次 REDUCE / SELL 成交价，至少偏离多少才允许下一次 SELL
SELL_PRICE_GAP_PCT = 0.02


# =========================
# Price Gap Direction Control
# =========================
# BUY 时是否允许“高于上次买点继续追”
ALLOW_BUY_ABOVE_LAST_BUY = True

# BUY 时是否允许“低于上次买点继续补”
ALLOW_BUY_BELOW_LAST_BUY = True

# REDUCE / SELL 时是否允许“高于上次卖点继续卖”
ALLOW_EXIT_ABOVE_LAST_EXIT = True

# REDUCE / SELL 时是否允许“低于上次卖点继续卖”
ALLOW_EXIT_BELOW_LAST_EXIT = True


# =========================
# Required Input Columns
# =========================
ACTION_SIGNAL_COL = "action_signal"
PRICE_COL = "close"


# =========================
# Validation / Parsing
# =========================
def _validate_required_columns(feature_df: pd.DataFrame) -> None:
    required_cols = [ACTION_SIGNAL_COL, PRICE_COL]
    missing = [c for c in required_cols if c not in feature_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for position engine: {missing}")


def _parse_action(value) -> ActionSignal:
    if isinstance(value, ActionSignal):
        return value

    if value is None:
        return ActionSignal.HOLD

    try:
        if pd.isna(value):
            return ActionSignal.HOLD
    except Exception:
        pass

    try:
        return ActionSignal(str(value).lower())
    except ValueError as exc:
        raise ValueError(f"Invalid action signal value: {value}") from exc


def _safe_float(value, default: float = 0.0) -> float:
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
# Size Helpers
# =========================
def _get_buy_size(current_position: int) -> int:
    if current_position >= MAX_POSITION:
        return 0

    if current_position == 0:
        return min(ENTRY_SIZE, MAX_POSITION - current_position)

    if ENTRY_ONLY_WHEN_FLAT:
        return 0

    return min(ADD_SIZE, MAX_POSITION - current_position)


def _get_reduce_size(current_position: int) -> int:
    if current_position <= MIN_POSITION:
        return 0

    return min(REDUCE_SIZE, current_position - MIN_POSITION)


def _get_sell_size(current_position: int) -> int:
    if current_position <= MIN_POSITION:
        return 0

    if SELL_ALL_ON_SELL:
        return current_position - MIN_POSITION

    return min(SELL_SIZE, current_position - MIN_POSITION)


# =========================
# Cooldown Helpers
# =========================
def _pass_buy_cooldown(
    current_time,
    last_buy_time,
) -> bool:
    if not ENABLE_POSITION_COOLDOWN:
        return True

    if last_buy_time is None:
        return True

    return (current_time - last_buy_time) >= BUY_COOLDOWN


def _pass_exit_cooldown(
    current_time,
    last_exit_time,
) -> bool:
    if not ENABLE_POSITION_COOLDOWN:
        return True

    if last_exit_time is None:
        return True

    return (current_time - last_exit_time) >= EXIT_COOLDOWN


# =========================
# Price Gap Helpers
# =========================
def _pct_diff(current_price: float, reference_price: float) -> float:
    if reference_price == 0:
        return 0.0
    return (current_price - reference_price) / reference_price


def _pass_buy_price_gap(
    current_price: float,
    last_buy_price: float | None,
) -> bool:
    if not ENABLE_PRICE_GAP:
        return True

    if last_buy_price is None:
        return True

    diff = _pct_diff(current_price, last_buy_price)
    abs_diff = abs(diff)

    if abs_diff < BUY_PRICE_GAP_PCT:
        return False

    if diff > 0 and not ALLOW_BUY_ABOVE_LAST_BUY:
        return False

    if diff < 0 and not ALLOW_BUY_BELOW_LAST_BUY:
        return False

    return True


def _pass_exit_price_gap(
    current_price: float,
    last_exit_price: float | None,
    required_gap_pct: float,
) -> bool:
    if not ENABLE_PRICE_GAP:
        return True

    if last_exit_price is None:
        return True

    diff = _pct_diff(current_price, last_exit_price)
    abs_diff = abs(diff)

    if abs_diff < required_gap_pct:
        return False

    if diff > 0 and not ALLOW_EXIT_ABOVE_LAST_EXIT:
        return False

    if diff < 0 and not ALLOW_EXIT_BELOW_LAST_EXIT:
        return False

    return True


# =========================
# Execution Rules
# =========================
def _try_execute_buy(
    current_position: int,
    current_time,
    current_price: float,
    last_buy_time,
    last_buy_price: float | None,
) -> tuple[ActionSignal, int]:
    size = _get_buy_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0

    if not _pass_buy_cooldown(current_time=current_time, last_buy_time=last_buy_time):
        return ActionSignal.HOLD, 0

    if not _pass_buy_price_gap(
        current_price=current_price,
        last_buy_price=last_buy_price,
    ):
        return ActionSignal.HOLD, 0

    return ActionSignal.BUY, size


def _try_execute_reduce(
    current_position: int,
    current_time,
    current_price: float,
    last_exit_time,
    last_exit_price: float | None,
) -> tuple[ActionSignal, int]:
    size = _get_reduce_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0

    if not _pass_exit_cooldown(
        current_time=current_time,
        last_exit_time=last_exit_time,
    ):
        return ActionSignal.HOLD, 0

    if not _pass_exit_price_gap(
        current_price=current_price,
        last_exit_price=last_exit_price,
        required_gap_pct=REDUCE_PRICE_GAP_PCT,
    ):
        return ActionSignal.HOLD, 0

    return ActionSignal.REDUCE, -size


def _try_execute_sell(
    current_position: int,
    current_time,
    current_price: float,
    last_exit_time,
    last_exit_price: float | None,
) -> tuple[ActionSignal, int]:
    size = _get_sell_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0

    if not _pass_exit_cooldown(
        current_time=current_time,
        last_exit_time=last_exit_time,
    ):
        return ActionSignal.HOLD, 0

    if not _pass_exit_price_gap(
        current_price=current_price,
        last_exit_price=last_exit_price,
        required_gap_pct=SELL_PRICE_GAP_PCT,
    ):
        return ActionSignal.HOLD, 0

    return ActionSignal.SELL, -size


# =========================
# Public API
# =========================
def compute_position_actions(
    feature_df: pd.DataFrame,
) -> pd.Series:
    """
    最简输出版：
    输入 action_signal + close
    输出 position_action 序列
    """
    result_df = compute_position_engine_frame(feature_df)
    return result_df["position_action"]


def compute_position_engine_frame(
    feature_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    更完整输出版：
    返回真正执行动作 + 仓位变化 + 仓位轨迹
    """
    _validate_required_columns(feature_df)

    current_position = INITIAL_POSITION

    last_buy_time = None
    last_exit_time = None

    last_buy_price: float | None = None
    last_exit_price: float | None = None

    position_actions: list[ActionSignal] = []
    position_deltas: list[int] = []
    position_sizes: list[int] = []
    executed_prices: list[float | None] = []

    for i in range(len(feature_df)):
        current_time = feature_df.index[i]
        current_signal = _parse_action(feature_df[ACTION_SIGNAL_COL].iloc[i])
        current_price = _safe_float(feature_df[PRICE_COL].iloc[i], default=0.0)

        execution_action = ActionSignal.HOLD
        delta_position = 0
        executed_price: float | None = None

        if current_signal == ActionSignal.BUY:
            execution_action, delta_position = _try_execute_buy(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_buy_time=last_buy_time,
                last_buy_price=last_buy_price,
            )

            if execution_action == ActionSignal.BUY:
                executed_price = current_price
                last_buy_time = current_time
                last_buy_price = current_price

        elif current_signal == ActionSignal.REDUCE:
            execution_action, delta_position = _try_execute_reduce(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_exit_time=last_exit_time,
                last_exit_price=last_exit_price,
            )

            if execution_action == ActionSignal.REDUCE:
                executed_price = current_price
                last_exit_time = current_time
                last_exit_price = current_price

        elif current_signal == ActionSignal.SELL:
            execution_action, delta_position = _try_execute_sell(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_exit_time=last_exit_time,
                last_exit_price=last_exit_price,
            )

            if execution_action == ActionSignal.SELL:
                executed_price = current_price
                last_exit_time = current_time
                last_exit_price = current_price

        elif current_signal == ActionSignal.AVOID:
            execution_action = ActionSignal.AVOID
            delta_position = 0

        current_position += delta_position

        if current_position < MIN_POSITION:
            current_position = MIN_POSITION
        if current_position > MAX_POSITION:
            current_position = MAX_POSITION

        position_actions.append(execution_action)
        position_deltas.append(delta_position)
        position_sizes.append(current_position)
        executed_prices.append(executed_price)

    return pd.DataFrame(
        {
            "position_action": position_actions,
            "position_delta": position_deltas,
            "position_size": position_sizes,
            "executed_price": executed_prices,
        },
        index=feature_df.index,
    )