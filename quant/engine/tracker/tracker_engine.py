from __future__ import annotations

from quant.engine.tracker.models import TrackerConfig
from quant.engine.tracker.tracker_core import PositionTracker


class PositionTrackerEngine:
    """
    对外统一入口。
    让上层只 import 这个类即可。
    """

    def __init__(
        self,
        symbol: str,
        initial_cash: float = 0.0,
        recent_window: int = 20,
        recent_reduce_window: int = 20,
        recent_sell_window: int = 20,
    ) -> None:
        self.tracker = PositionTracker(
            symbol=symbol,
            config=TrackerConfig(
                initial_cash=initial_cash,
                recent_window=recent_window,
                recent_reduce_window=recent_reduce_window,
                recent_sell_window=recent_sell_window,
            ),
        )

    # ========== write ==========
    def on_bar(self, timestamp, price: float) -> None:
        self.tracker.on_bar(timestamp=timestamp, price=price)

    def on_buy(
        self,
        timestamp,
        qty: int,
        price: float,
        entry_reason: str = "buy",
        entry_signal: str = "",
        entry_regime: str = "",
        entry_atr: float | None = None,
    ):
        return self.tracker.on_buy(
            timestamp=timestamp,
            qty=qty,
            price=price,
            entry_reason=entry_reason,
            entry_signal=entry_signal,
            entry_regime=entry_regime,
            entry_atr=entry_atr,
        )

    def on_reduce(
        self,
        timestamp,
        qty: int,
        price: float,
        exit_reason: str = "reduce",
        exit_regime: str = "",
    ):
        return self.tracker.on_reduce(
            timestamp=timestamp,
            qty=qty,
            price=price,
            exit_reason=exit_reason,
            exit_regime=exit_regime,
        )

    def on_sell(
        self,
        timestamp,
        qty: int,
        price: float,
        exit_reason: str = "sell",
        exit_regime: str = "",
    ):
        return self.tracker.on_sell(
            timestamp=timestamp,
            qty=qty,
            price=price,
            exit_reason=exit_reason,
            exit_regime=exit_regime,
        )

    def on_force_exit(
        self,
        timestamp,
        price: float,
        exit_reason: str = "force_exit",
        exit_regime: str = "",
    ):
        return self.tracker.on_force_exit(
            timestamp=timestamp,
            price=price,
            exit_reason=exit_reason,
            exit_regime=exit_regime,
        )

    # ========== read ==========
    def get_snapshot(self):
        return self.tracker.get_snapshot()

    def get_open_lots(self):
        return self.tracker.get_open_lots()

    def get_closed_trades(self):
        return self.tracker.get_closed_trades()

    def get_recent_trade_stats(self):
        return self.tracker.get_recent_trade_stats()

    def get_recent_reduce_stats(self):
        return self.tracker.get_recent_reduce_stats()

    def get_recent_sell_stats(self):
        return self.tracker.get_recent_sell_stats()

    @property
    def current_position_qty(self) -> int:
        return self.tracker.current_position_qty

    @property
    def avg_cost(self) -> float:
        return self.tracker.avg_cost

    def reset(self) -> None:
        self.tracker.reset()