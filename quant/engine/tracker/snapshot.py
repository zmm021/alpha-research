from __future__ import annotations

from dataclasses import dataclass

from quant.engine.tracker.models import TradeStats


@dataclass
class TrackerSnapshot:
    symbol: str
    timestamp: object | None

    current_price: float
    cash: float
    market_value: float
    equity: float

    realized_pnl_total: float
    unrealized_pnl_total: float

    equity_peak: float
    current_drawdown: float
    max_drawdown: float

    current_position_qty: int
    avg_cost: float

    open_lot_count: int
    closed_trade_count: int

    worst_open_lot_pnl: float
    best_open_lot_pnl: float
    worst_open_lot_mae: float
    best_open_lot_mfe: float

    recent_trade_stats: TradeStats
    recent_reduce_stats: TradeStats
    recent_sell_stats: TradeStats

    last_executed_action: str | None
    last_executed_action_time: object | None