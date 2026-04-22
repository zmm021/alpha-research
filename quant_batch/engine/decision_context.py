from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from quant.engine.tracker.snapshot import TrackerSnapshot
from quant.engine.regime_engine import (
    compute_regime_with_quality,
    MarketRegime,
    RegimeQuality,
)


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

    # ===== market =====
    symbol_state: str
    regime: MarketRegime
    regime_quality: RegimeQuality
    regime_score: float

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
    # ===== execution memory（🔥 NEW）=====
    last_executed_action: str
    last_executed_action_time: object | None
    # ===== derived =====
    has_position: bool
    is_losing_position: bool

    # ===== helper flags =====
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
    - market state（当前先用 symbol_state 为主）

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
        sector_state: Optional[str] = None,
        macro_state: Optional[str] = None,
        range_position: Optional[float] = None,
        trend_slope: Optional[float] = None,
        long_slope: Optional[float] = None,
    ) -> DecisionContext:

        alpha_signal = _normalize_str(alpha_signal)
        symbol_state = _normalize_str(symbol_state)
        sector_state = _normalize_str(sector_state)
        macro_state = _normalize_str(macro_state)

        # ===== unified regime + quality =====
        regime, regime_quality, regime_score = compute_regime_with_quality(
            symbol_state=symbol_state,
            sector_state=sector_state,
            macro_state=macro_state,
            range_position=range_position,
            trend_slope=trend_slope,
            long_slope=long_slope,
        )
         
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
        # V1 penalty logic
        # =========================================================

        # 1. reduce 表现差 → 只限制，不一定完全禁
        disable_reduce = recent_reduce_median_pnl < 0

        # 2. recent trade 差 → buy 变保守
        cautious_buy = (
            recent_trade_median_pnl < 0
            or recent_trade_consecutive_losses >= 2
        )

        # 3. defensive mode（当前先关闭，后面再升级）
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
            regime=regime,
            regime_quality=regime_quality,
            regime_score=_safe_float(regime_score),

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
            last_executed_action = tracker_snapshot.last_executed_action or "",
            last_executed_action_time = tracker_snapshot.last_executed_action_time,
            # derived
            has_position=has_position,
            is_losing_position=is_losing_position,

            # flags
            disable_reduce=disable_reduce,
            cautious_buy=cautious_buy,
            defensive_mode=defensive_mode,
        )