from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from quant.engine.tracker.snapshot import TrackerSnapshot


def _safe_str(v) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""
def _normalize_str(v) -> str:
    if v is None:
        return ""

    # Enum like ActionSignal.BUY / SymbolState.TREND_EARLY
    if hasattr(v, "value"):
        return str(v.value).strip().lower()

    s = str(v).strip().lower()

    # handle strings like "ActionSignal.BUY" / "SymbolState.TREND_EARLY"
    if "." in s:
        s = s.split(".")[-1]

    return s

def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


# =========================================================
# Decision Context
# =========================================================

@dataclass
class DecisionContext:
    # ===== identity =====
    symbol: str
    timestamp: object | None

    # ===== price =====
    price: float

    # ===== alpha =====
    alpha_signal: str  # buy / hold / reduce / sell / avoid

    # ===== market (简化版，先用 symbol_state) =====
    symbol_state: str  # trend / range / downtrend / risk 等（你自己定义）

    # ===== tracker / account =====
    current_position_qty: int
    avg_cost: float

    realized_pnl_total: float
    unrealized_pnl_total: float

    equity: float
    current_drawdown: float
    max_drawdown: float

    # ===== performance =====
    recent_trade_win_rate: float
    recent_trade_median_pnl: float
    recent_trade_consecutive_losses: int

    recent_reduce_win_rate: float
    recent_reduce_median_pnl: float
    recent_reduce_consecutive_losses: int

    # ===== derived (轻量推导，不做复杂逻辑) =====
    has_position: bool
    is_losing_position: bool

    # ===== helper flags (给 engine 用) =====
    disable_reduce: bool
    cautious_buy: bool
    defensive_mode: bool


# =========================================================
# Builder
# =========================================================

class DecisionContextBuilder:
    """
    负责把：
    - alpha signal
    - tracker snapshot
    - market state（你现在先传 symbol_state）

    拼成一个统一 context
    """

    def build(
        self,
        symbol: str,
        timestamp,
        price: float,
        alpha_signal,
        symbol_state: str,
        tracker_snapshot: TrackerSnapshot,
    ) -> DecisionContext:

        alpha_signal = _normalize_str(alpha_signal).lower()
        symbol_state = _normalize_str(symbol_state).lower()

        # ===== performance =====
        trade_stats = tracker_snapshot.recent_trade_stats
        reduce_stats = tracker_snapshot.recent_reduce_stats

        recent_trade_win_rate = _safe_float(trade_stats.win_rate)
        recent_trade_median_pnl = _safe_float(trade_stats.median_pnl)
        recent_trade_consecutive_losses = _safe_int(trade_stats.consecutive_losses)

        recent_reduce_win_rate = _safe_float(reduce_stats.win_rate)
        recent_reduce_median_pnl = _safe_float(reduce_stats.median_pnl)
        recent_reduce_consecutive_losses = _safe_int(reduce_stats.consecutive_losses)

        # ===== basic position state =====
        has_position = tracker_snapshot.current_position_qty > 0
        is_losing_position = tracker_snapshot.unrealized_pnl_total < 0

        # =========================================================
        # V1 惩罚逻辑（轻量版，不做复杂 if）
        # =========================================================

        # 1️⃣ disable reduce（做T失效）
        disable_reduce = recent_reduce_median_pnl < 0

        # 2️⃣ cautious buy（买入变保守）
        cautious_buy = (
            recent_trade_median_pnl < 0
            or recent_trade_consecutive_losses >= 2
        )

        # 3️⃣ defensive mode（整体收缩）
       # defensive_mode = (
        #    recent_trade_consecutive_losses >= 3
        #    or tracker_snapshot.current_drawdown < -0.05 * tracker_snapshot.equity_peak
        #)
        defensive_mode = False
        return DecisionContext(
            # identity
            symbol=symbol,
            timestamp=timestamp,

            # price
            price=_safe_float(price),

            # alpha
            alpha_signal=alpha_signal,

            # market
            symbol_state=symbol_state,

            # position
            current_position_qty=tracker_snapshot.current_position_qty,
            avg_cost=tracker_snapshot.avg_cost,

            realized_pnl_total=tracker_snapshot.realized_pnl_total,
            unrealized_pnl_total=tracker_snapshot.unrealized_pnl_total,

            equity=tracker_snapshot.equity,
            current_drawdown=tracker_snapshot.current_drawdown,
            max_drawdown=tracker_snapshot.max_drawdown,

            # performance
            recent_trade_win_rate=recent_trade_win_rate,
            recent_trade_median_pnl=recent_trade_median_pnl,
            recent_trade_consecutive_losses=recent_trade_consecutive_losses,

            recent_reduce_win_rate=recent_reduce_win_rate,
            recent_reduce_median_pnl=recent_reduce_median_pnl,
            recent_reduce_consecutive_losses=recent_reduce_consecutive_losses,

            # derived
            has_position=has_position,
            is_losing_position=is_losing_position,

            # flags
            disable_reduce=disable_reduce,
            cautious_buy=cautious_buy,
            defensive_mode=defensive_mode,
        )