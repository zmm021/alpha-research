from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S4PositionContext:
    current_position_qty: int = 0
    avg_cost: float = 0.0

    realized_pnl_total: float = 0.0
    unrealized_pnl_total: float = 0.0

    equity: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0

    recent_trade_win_rate: float = 0.0
    recent_trade_median_pnl: float = 0.0
    recent_trade_consecutive_losses: int = 0

    recent_reduce_win_rate: float = 0.0
    recent_reduce_median_pnl: float = 0.0
    recent_reduce_consecutive_losses: int = 0

    last_executed_action: str = ""
    last_executed_action_time: object | None = None

    has_position: bool = False
    is_losing_position: bool = False

    disable_reduce: bool = False
    cautious_buy: bool = False

    proposal_action: str = ""
    proposal_qty: int = 0
    proposal_reason: str = ""