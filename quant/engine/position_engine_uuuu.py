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

SELL_ALL_ON_SELL = False
ENTRY_ONLY_WHEN_FLAT = False

# 每个 cycle 最多执行几次 BUY
MAX_BUY_COUNT_PER_CYCLE = 5

# 当前价格低于成本多少时，禁止继续 BUY
# 例如 0.05 表示低于成本 5% 后不再补
ENABLE_LOSS_GUARD = True
MAX_LOSS_TO_ALLOW_BUY = 0.05

# 高仓位区是否降低继续 BUY 的能力
ENABLE_POSITION_ZONE_GATING = True
HIGH_POSITION_THRESHOLD = 0.8  # >= 80% max_position 视为高仓位
ALLOW_BUY_IN_HIGH_POSITION = False


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

BUY_PRICE_GAP_PCT = 0.02
REDUCE_PRICE_GAP_PCT = 0.02
SELL_PRICE_GAP_PCT = 0.02


# =========================
# Price Gap Direction Control
# =========================
ALLOW_BUY_ABOVE_LAST_BUY = True
ALLOW_BUY_BELOW_LAST_BUY = True

ALLOW_EXIT_ABOVE_LAST_EXIT = True
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
# Cost / PnL Helpers
# =========================
def _update_avg_cost_after_buy(
    current_position: int,
    avg_cost: float | None,
    buy_price: float,
    buy_qty: int,
) -> float | None:
    if buy_qty <= 0:
        return avg_cost

    if current_position <= 0 or avg_cost is None:
        return buy_price

    total_cost_before = avg_cost * current_position
    total_cost_after = total_cost_before + buy_price * buy_qty
    new_position = current_position + buy_qty

    if new_position <= 0:
        return None

    return total_cost_after / new_position


def _update_avg_cost_after_sell(
    new_position: int,
    avg_cost: float | None,
) -> float | None:
    if new_position <= 0:
        return None
    return avg_cost


def _compute_unrealized_pnl_pct(
    current_price: float,
    avg_cost: float | None,
) -> float | None:
    if avg_cost is None or avg_cost <= 0:
        return None
    return (current_price - avg_cost) / avg_cost


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
def _pass_buy_cooldown(current_time, last_buy_time) -> bool:
    if not ENABLE_POSITION_COOLDOWN:
        return True
    if last_buy_time is None:
        return True
    return (current_time - last_buy_time) >= BUY_COOLDOWN


def _pass_exit_cooldown(current_time, last_exit_time) -> bool:
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
# Position Zone / Guards
# =========================
def _in_high_position_zone(current_position: int) -> bool:
    if MAX_POSITION <= 0:
        return False
    return (current_position / MAX_POSITION) >= HIGH_POSITION_THRESHOLD


def _pass_position_zone_buy_gate(current_position: int) -> bool:
    if not ENABLE_POSITION_ZONE_GATING:
        return True

    if _in_high_position_zone(current_position) and not ALLOW_BUY_IN_HIGH_POSITION:
        return False

    return True


def _pass_loss_guard_for_buy(
    current_price: float,
    avg_cost: float | None,
) -> bool:
    if not ENABLE_LOSS_GUARD:
        return True

    pnl_pct = _compute_unrealized_pnl_pct(current_price=current_price, avg_cost=avg_cost)
    if pnl_pct is None:
        return True

    return pnl_pct >= -MAX_LOSS_TO_ALLOW_BUY


# =========================
# Execution Rules
# =========================
def _try_execute_buy(
    current_position: int,
    current_time,
    current_price: float,
    last_buy_time,
    last_buy_price: float | None,
    avg_cost: float | None,
    buy_count_since_reset: int,
) -> tuple[ActionSignal, int, str]:
    if buy_count_since_reset >= MAX_BUY_COUNT_PER_CYCLE:
        return ActionSignal.HOLD, 0, "buy_blocked_by_max_buy_count"

    size = _get_buy_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0, "buy_blocked_by_max_position"

    if not _pass_position_zone_buy_gate(current_position=current_position):
        return ActionSignal.HOLD, 0, "buy_blocked_by_position_zone"

    if not _pass_loss_guard_for_buy(current_price=current_price, avg_cost=avg_cost):
        return ActionSignal.HOLD, 0, "buy_blocked_by_loss_guard"

    if not _pass_buy_cooldown(current_time=current_time, last_buy_time=last_buy_time):
        return ActionSignal.HOLD, 0, "buy_blocked_by_cooldown"

    if not _pass_buy_price_gap(
        current_price=current_price,
        last_buy_price=last_buy_price,
    ):
        return ActionSignal.HOLD, 0, "buy_blocked_by_price_gap"

    return ActionSignal.BUY, size, "buy_executed"


def _try_execute_reduce(
    current_position: int,
    current_time,
    current_price: float,
    last_exit_time,
    last_exit_price: float | None,
) -> tuple[ActionSignal, int, str]:
    size = _get_reduce_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0, "reduce_blocked_by_no_position"

    if not _pass_exit_cooldown(
        current_time=current_time,
        last_exit_time=last_exit_time,
    ):
        return ActionSignal.HOLD, 0, "reduce_blocked_by_cooldown"

    if not _pass_exit_price_gap(
        current_price=current_price,
        last_exit_price=last_exit_price,
        required_gap_pct=REDUCE_PRICE_GAP_PCT,
    ):
        return ActionSignal.HOLD, 0, "reduce_blocked_by_price_gap"

    return ActionSignal.REDUCE, -size, "reduce_executed"


def _try_execute_sell(
    current_position: int,
    current_time,
    current_price: float,
    last_exit_time,
    last_exit_price: float | None,
) -> tuple[ActionSignal, int, str]:
    size = _get_sell_size(current_position)
    if size <= 0:
        return ActionSignal.HOLD, 0, "sell_blocked_by_no_position"

    if not _pass_exit_cooldown(
        current_time=current_time,
        last_exit_time=last_exit_time,
    ):
        return ActionSignal.HOLD, 0, "sell_blocked_by_cooldown"

    if not _pass_exit_price_gap(
        current_price=current_price,
        last_exit_price=last_exit_price,
        required_gap_pct=SELL_PRICE_GAP_PCT,
    ):
        return ActionSignal.HOLD, 0, "sell_blocked_by_price_gap"

    return ActionSignal.SELL, -size, "sell_executed"


# =========================
# Public API
# =========================
def compute_position_actions(
    feature_df: pd.DataFrame,
) -> pd.Series:
    result_df = compute_position_engine_frame(feature_df)
    return result_df["position_action"]


def compute_position_engine_frame(
    feature_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    增强版 position engine：
    返回真正执行动作 + 仓位变化 + 仓位轨迹 + 调试字段
    """
    _validate_required_columns(feature_df)

    current_position = INITIAL_POSITION
    avg_cost: float | None = None

    last_buy_time = None
    last_exit_time = None

    last_buy_price: float | None = None
    last_exit_price: float | None = None

    buy_count_since_reset = 0
    sell_count_since_reset = 0

    position_actions: list[ActionSignal] = []
    position_deltas: list[int] = []
    position_sizes: list[int] = []
    executed_prices: list[float | None] = []
    avg_costs: list[float | None] = []
    unrealized_pnl_pcts: list[float | None] = []
    execution_reasons: list[str] = []
    buy_counts: list[int] = []
    sell_counts: list[int] = []

    for i in range(len(feature_df)):
        current_time = feature_df.index[i]
        current_signal = _parse_action(feature_df[ACTION_SIGNAL_COL].iloc[i])
        current_price = _safe_float(feature_df[PRICE_COL].iloc[i], default=0.0)

        execution_action = ActionSignal.HOLD
        delta_position = 0
        executed_price: float | None = None
        execution_reason = "hold_no_action"

        if current_signal == ActionSignal.BUY:
            execution_action, delta_position, execution_reason = _try_execute_buy(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_buy_time=last_buy_time,
                last_buy_price=last_buy_price,
                avg_cost=avg_cost,
                buy_count_since_reset=buy_count_since_reset,
            )

            if execution_action == ActionSignal.BUY:
                executed_price = current_price
                buy_qty = delta_position

                avg_cost = _update_avg_cost_after_buy(
                    current_position=current_position,
                    avg_cost=avg_cost,
                    buy_price=current_price,
                    buy_qty=buy_qty,
                )

                current_position += delta_position

                last_buy_time = current_time
                last_buy_price = current_price
                buy_count_since_reset += 1

        elif current_signal == ActionSignal.REDUCE:
            execution_action, delta_position, execution_reason = _try_execute_reduce(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_exit_time=last_exit_time,
                last_exit_price=last_exit_price,
            )

            if execution_action == ActionSignal.REDUCE:
                executed_price = current_price
                current_position += delta_position

                avg_cost = _update_avg_cost_after_sell(
                    new_position=current_position,
                    avg_cost=avg_cost,
                )

                last_exit_time = current_time
                last_exit_price = current_price
                sell_count_since_reset += 1

        elif current_signal == ActionSignal.SELL:
            execution_action, delta_position, execution_reason = _try_execute_sell(
                current_position=current_position,
                current_time=current_time,
                current_price=current_price,
                last_exit_time=last_exit_time,
                last_exit_price=last_exit_price,
            )

            if execution_action == ActionSignal.SELL:
                executed_price = current_price
                current_position += delta_position

                avg_cost = _update_avg_cost_after_sell(
                    new_position=current_position,
                    avg_cost=avg_cost,
                )

                last_exit_time = current_time
                last_exit_price = current_price
                sell_count_since_reset += 1

        elif current_signal == ActionSignal.AVOID:
            execution_action = ActionSignal.AVOID
            delta_position = 0
            execution_reason = "avoid_forwarded"

        else:
            execution_reason = "hold_forwarded"

        if current_position < MIN_POSITION:
            current_position = MIN_POSITION
        if current_position > MAX_POSITION:
            current_position = MAX_POSITION

        # 仓位归零，重置 cycle 计数
        if current_position == 0:
            avg_cost = None
            buy_count_since_reset = 0
            sell_count_since_reset = 0

        unrealized_pnl_pct = _compute_unrealized_pnl_pct(
            current_price=current_price,
            avg_cost=avg_cost,
        )

        position_actions.append(execution_action)
        position_deltas.append(delta_position)
        position_sizes.append(current_position)
        executed_prices.append(executed_price)
        avg_costs.append(avg_cost)
        unrealized_pnl_pcts.append(unrealized_pnl_pct)
        execution_reasons.append(execution_reason)
        buy_counts.append(buy_count_since_reset)
        sell_counts.append(sell_count_since_reset)

    return pd.DataFrame(
        {
            "position_action": position_actions,
            "position_delta": position_deltas,
            "position_size": position_sizes,
            "executed_price": executed_prices,
            "position_avg_cost": avg_costs,
            "position_unrealized_pnl_pct": unrealized_pnl_pcts,
            "execution_reason": execution_reasons,
            "buy_count_since_reset": buy_counts,
            "sell_count_since_reset": sell_counts,
        },
        index=feature_df.index,
    )