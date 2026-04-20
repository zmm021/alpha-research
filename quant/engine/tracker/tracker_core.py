from __future__ import annotations

from collections import deque
from statistics import median
from typing import Iterable

from quant.engine.tracker.models import (
    ClosedTrade,
    PositionLot,
    TrackerConfig,
    TradeStats,
)
from quant.engine.tracker.snapshot import TrackerSnapshot


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_action(value) -> str:
    if value is None:
        return ""

    if hasattr(value, "value"):
        return str(value.value).lower()

    s = str(value).strip().lower()
    if "." in s:
        s = s.split(".")[-1]
    return s


class PositionTracker:
    """
    纯账本 / 仓位生命周期管理器。
    不负责生成交易信号，只负责：
    - 开仓登记
    - FIFO 平仓配对
    - bar 级 mark-to-market
    - 账户权益 / 回撤
    - 最近交易表现统计
    """

    def __init__(self, symbol: str, config: TrackerConfig | None = None) -> None:
        self.symbol = symbol
        self.config = config or TrackerConfig()

        self._next_lot_id = 1
        self._next_trade_id = 1

        self.open_lots: list[PositionLot] = []
        self.closed_trades: list[ClosedTrade] = []

        self.cash: float = self.config.initial_cash
        self.current_price: float = 0.0
        self.current_time = None

        self.realized_pnl_total: float = 0.0
        self.unrealized_pnl_total: float = 0.0

        self.equity: float = self.cash
        self.equity_peak: float = self.equity
        self.current_drawdown: float = 0.0
        self.max_drawdown: float = 0.0

        self._recent_pnls: deque[float] = deque(maxlen=self.config.recent_window)
        self._recent_reduce_pnls: deque[float] = deque(maxlen=self.config.recent_reduce_window)
        self._recent_sell_pnls: deque[float] = deque(maxlen=self.config.recent_sell_window)

    # =========================
    # Public write APIs
    # =========================
    def on_bar(self, timestamp, price: float) -> None:
        self.current_time = timestamp
        self.current_price = _safe_float(price)

        for lot in self.open_lots:
            lot.update_mark(self.current_price)

        self._refresh_account_state()

    def on_buy(
        self,
        timestamp,
        qty: int,
        price: float,
        entry_reason: str = "buy",
        entry_signal: str = "",
        entry_regime: str = "",
        entry_atr: float | None = None,
    ) -> PositionLot:
        qty = int(qty)
        if qty <= 0:
            raise ValueError("BUY qty must be > 0")

        price = _safe_float(price)
        lot = PositionLot(
            lot_id=self._next_lot_id,
            symbol=self.symbol,
            entry_time=timestamp,
            entry_price=price,
            qty_original=qty,
            qty_open=qty,
            entry_reason=entry_reason,
            entry_signal=entry_signal,
            entry_regime=entry_regime,
            entry_atr=entry_atr,
        )
        self._next_lot_id += 1
        self.open_lots.append(lot)

        self.cash -= qty * price
        self.current_time = timestamp
        self.current_price = price
        self._refresh_account_state()
        return lot

    def on_reduce(
        self,
        timestamp,
        qty: int,
        price: float,
        exit_reason: str = "reduce",
        exit_regime: str = "",
    ) -> list[ClosedTrade]:
        return self._close_fifo(
            timestamp=timestamp,
            qty=qty,
            price=price,
            exit_action="reduce",
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
    ) -> list[ClosedTrade]:
        return self._close_fifo(
            timestamp=timestamp,
            qty=qty,
            price=price,
            exit_action="sell",
            exit_reason=exit_reason,
            exit_regime=exit_regime,
        )

    def on_force_exit(
        self,
        timestamp,
        price: float,
        exit_reason: str = "force_exit",
        exit_regime: str = "",
    ) -> list[ClosedTrade]:
        qty = self.current_position_qty
        if qty <= 0:
            return []
        return self._close_fifo(
            timestamp=timestamp,
            qty=qty,
            price=price,
            exit_action="force_exit",
            exit_reason=exit_reason,
            exit_regime=exit_regime,
        )

    # =========================
    # Public read APIs
    # =========================
    @property
    def current_position_qty(self) -> int:
        return sum(lot.qty_open for lot in self.open_lots)

    @property
    def avg_cost(self) -> float:
        total_qty = self.current_position_qty
        if total_qty <= 0:
            return 0.0
        total_cost = sum(lot.entry_price * lot.qty_open for lot in self.open_lots)
        return total_cost / total_qty

    def get_open_lots(self) -> list[PositionLot]:
        return list(self.open_lots)

    def get_closed_trades(self) -> list[ClosedTrade]:
        return list(self.closed_trades)

    def get_recent_trade_stats(self) -> TradeStats:
        return self._build_trade_stats(self._recent_pnls)

    def get_recent_reduce_stats(self) -> TradeStats:
        return self._build_trade_stats(self._recent_reduce_pnls)

    def get_recent_sell_stats(self) -> TradeStats:
        return self._build_trade_stats(self._recent_sell_pnls)

    def get_snapshot(self) -> TrackerSnapshot:
        worst_open = min((lot.unrealized_pnl for lot in self.open_lots), default=0.0)
        best_open = max((lot.unrealized_pnl for lot in self.open_lots), default=0.0)
        worst_mae = min((lot.mae for lot in self.open_lots), default=0.0)
        best_mfe = max((lot.mfe for lot in self.open_lots), default=0.0)

        return TrackerSnapshot(
            symbol=self.symbol,
            timestamp=self.current_time,
            current_price=self.current_price,
            cash=self.cash,
            market_value=self.current_position_qty * self.current_price,
            equity=self.equity,
            realized_pnl_total=self.realized_pnl_total,
            unrealized_pnl_total=self.unrealized_pnl_total,
            equity_peak=self.equity_peak,
            current_drawdown=self.current_drawdown,
            max_drawdown=self.max_drawdown,
            current_position_qty=self.current_position_qty,
            avg_cost=self.avg_cost,
            open_lot_count=len(self.open_lots),
            closed_trade_count=len(self.closed_trades),
            worst_open_lot_pnl=worst_open,
            best_open_lot_pnl=best_open,
            worst_open_lot_mae=worst_mae,
            best_open_lot_mfe=best_mfe,
            recent_trade_stats=self.get_recent_trade_stats(),
            recent_reduce_stats=self.get_recent_reduce_stats(),
            recent_sell_stats=self.get_recent_sell_stats(),
        )

    def reset(self) -> None:
        self.__init__(symbol=self.symbol, config=self.config)

    # =========================
    # Internal helpers
    # =========================
    def _close_fifo(
        self,
        timestamp,
        qty: int,
        price: float,
        exit_action: str,
        exit_reason: str,
        exit_regime: str,
    ) -> list[ClosedTrade]:
        qty = int(qty)
        if qty <= 0:
            return []

        price = _safe_float(price)
        self.current_time = timestamp
        self.current_price = price

        remaining = qty
        closed: list[ClosedTrade] = []

        while remaining > 0 and self.open_lots:
            lot = self.open_lots[0]
            matched_qty = min(lot.qty_open, remaining)

            pnl = (price - lot.entry_price) * matched_qty
            pnl_pct = 0.0
            if lot.entry_price > 0:
                pnl_pct = (price - lot.entry_price) / lot.entry_price

            trade = ClosedTrade(
                trade_id=self._next_trade_id,
                lot_id=lot.lot_id,
                symbol=self.symbol,
                entry_time=lot.entry_time,
                exit_time=timestamp,
                qty=matched_qty,
                entry_price=lot.entry_price,
                exit_price=price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                entry_reason=lot.entry_reason,
                entry_signal=lot.entry_signal,
                entry_regime=lot.entry_regime,
                exit_action=exit_action,
                exit_reason=exit_reason,
                exit_regime=exit_regime,
                lot_mfe=lot.mfe,
                lot_mae=lot.mae,
            )
            self._next_trade_id += 1
            self.closed_trades.append(trade)
            closed.append(trade)

            self.realized_pnl_total += pnl
            self.cash += matched_qty * price

            self._recent_pnls.append(pnl)
            if exit_action == "reduce":
                self._recent_reduce_pnls.append(pnl)
            elif exit_action in {"sell", "force_exit"}:
                self._recent_sell_pnls.append(pnl)

            lot.qty_open -= matched_qty
            remaining -= matched_qty

            if lot.qty_open <= 0:
                self.open_lots.pop(0)

        self._refresh_account_state()
        return closed

    def _refresh_account_state(self) -> None:
        self.unrealized_pnl_total = sum(lot.unrealized_pnl for lot in self.open_lots)
        market_value = self.current_position_qty * self.current_price
        self.equity = self.cash + market_value

        self.equity_peak = max(self.equity_peak, self.equity)
        self.current_drawdown = self.equity - self.equity_peak
        self.max_drawdown = min(self.max_drawdown, self.current_drawdown)

    def _build_trade_stats(self, pnl_values: Iterable[float]) -> TradeStats:
        values = list(pnl_values)
        if not values:
            return TradeStats()

        wins = [x for x in values if x > 0]
        losses = [x for x in values if x < 0]

        consecutive_losses = 0
        for x in reversed(values):
            if x < 0:
                consecutive_losses += 1
            else:
                break

        return TradeStats(
            count=len(values),
            total_pnl=sum(values),
            win_rate=(len(wins) / len(values)) if values else 0.0,
            avg_pnl=(sum(values) / len(values)) if values else 0.0,
            median_pnl=median(values) if values else 0.0,
            avg_win=(sum(wins) / len(wins)) if wins else 0.0,
            avg_loss=(sum(losses) / len(losses)) if losses else 0.0,
            max_win=max(values) if values else 0.0,
            max_loss=min(values) if values else 0.0,
            consecutive_losses=consecutive_losses,
        )