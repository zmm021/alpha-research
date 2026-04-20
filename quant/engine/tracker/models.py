from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PositionLot:
    """
    单笔开仓 lot，对应一次 buy 建仓。
    qty_open 会随着 reduce / sell / force_exit 被逐步消耗。
    """
    lot_id: int
    symbol: str
    entry_time: object
    entry_price: float
    qty_original: int
    qty_open: int

    entry_reason: str = "buy"
    entry_signal: str = ""
    entry_regime: str = ""
    entry_atr: Optional[float] = None

    last_price: Optional[float] = None
    holding_bars: int = 0

    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    mfe: float = 0.0
    mae: float = 0.0

    def update_mark(self, price: float) -> None:
        self.last_price = price
        self.holding_bars += 1

        pnl = (price - self.entry_price) * self.qty_open
        self.unrealized_pnl = pnl

        if self.entry_price > 0:
            self.unrealized_pnl_pct = (price - self.entry_price) / self.entry_price
        else:
            self.unrealized_pnl_pct = 0.0

        self.mfe = max(self.mfe, pnl)
        self.mae = min(self.mae, pnl)

    @property
    def is_open(self) -> bool:
        return self.qty_open > 0


@dataclass
class ClosedTrade:
    """
    FIFO 配对后的已平仓成交片段。
    一次 sell / reduce 可能匹配多个 open lots，因此会生成多个 ClosedTrade。
    """
    trade_id: int
    lot_id: int
    symbol: str

    entry_time: object
    exit_time: object

    qty: int
    entry_price: float
    exit_price: float

    pnl: float
    pnl_pct: float

    entry_reason: str = ""
    entry_signal: str = ""
    entry_regime: str = ""

    exit_action: str = ""
    exit_reason: str = ""
    exit_regime: str = ""

    lot_mfe: float = 0.0
    lot_mae: float = 0.0


@dataclass
class TrackerConfig:
    """
    最小配置。
    """
    initial_cash: float = 0.0
    recent_window: int = 20
    recent_reduce_window: int = 20
    recent_sell_window: int = 20


@dataclass
class TradeStats:
    count: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    median_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    consecutive_losses: int = 0