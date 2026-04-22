
from __future__ import annotations

from quant.engine.tracker import PositionTrackerEngine


def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_snapshot(tracker: PositionTrackerEngine, label: str) -> None:
    snap = tracker.get_snapshot()

    print(f"\n[{label}]")
    print(f"timestamp:              {snap.timestamp}")
    print(f"current_price:          {snap.current_price:.2f}")
    print(f"cash:                   {snap.cash:.2f}")
    print(f"market_value:           {snap.market_value:.2f}")
    print(f"equity:                 {snap.equity:.2f}")
    print(f"realized_pnl_total:     {snap.realized_pnl_total:.2f}")
    print(f"unrealized_pnl_total:   {snap.unrealized_pnl_total:.2f}")
    print(f"equity_peak:            {snap.equity_peak:.2f}")
    print(f"current_drawdown:       {snap.current_drawdown:.2f}")
    print(f"max_drawdown:           {snap.max_drawdown:.2f}")
    print(f"current_position_qty:   {snap.current_position_qty}")
    print(f"avg_cost:               {snap.avg_cost:.4f}")
    print(f"open_lot_count:         {snap.open_lot_count}")
    print(f"closed_trade_count:     {snap.closed_trade_count}")
    print(f"worst_open_lot_pnl:     {snap.worst_open_lot_pnl:.2f}")
    print(f"best_open_lot_pnl:      {snap.best_open_lot_pnl:.2f}")
    print(f"worst_open_lot_mae:     {snap.worst_open_lot_mae:.2f}")
    print(f"best_open_lot_mfe:      {snap.best_open_lot_mfe:.2f}")

    print("\n  recent_trade_stats:")
    print(f"    count:              {snap.recent_trade_stats.count}")
    print(f"    total_pnl:          {snap.recent_trade_stats.total_pnl:.2f}")
    print(f"    win_rate:           {snap.recent_trade_stats.win_rate:.2%}")
    print(f"    avg_pnl:            {snap.recent_trade_stats.avg_pnl:.2f}")
    print(f"    median_pnl:         {snap.recent_trade_stats.median_pnl:.2f}")
    print(f"    avg_win:            {snap.recent_trade_stats.avg_win:.2f}")
    print(f"    avg_loss:           {snap.recent_trade_stats.avg_loss:.2f}")
    print(f"    max_win:            {snap.recent_trade_stats.max_win:.2f}")
    print(f"    max_loss:           {snap.recent_trade_stats.max_loss:.2f}")
    print(f"    consecutive_losses: {snap.recent_trade_stats.consecutive_losses}")

    print("\n  recent_reduce_stats:")
    print(f"    count:              {snap.recent_reduce_stats.count}")
    print(f"    total_pnl:          {snap.recent_reduce_stats.total_pnl:.2f}")
    print(f"    win_rate:           {snap.recent_reduce_stats.win_rate:.2%}")
    print(f"    median_pnl:         {snap.recent_reduce_stats.median_pnl:.2f}")

    print("\n  recent_sell_stats:")
    print(f"    count:              {snap.recent_sell_stats.count}")
    print(f"    total_pnl:          {snap.recent_sell_stats.total_pnl:.2f}")
    print(f"    win_rate:           {snap.recent_sell_stats.win_rate:.2%}")
    print(f"    median_pnl:         {snap.recent_sell_stats.median_pnl:.2f}")


def print_open_lots(tracker: PositionTrackerEngine) -> None:
    lots = tracker.get_open_lots()

    print("\nOpen Lots:")
    if not lots:
        print("  <none>")
        return

    for lot in lots:
        print(
            f"  lot_id={lot.lot_id} "
            f"entry_time={lot.entry_time} "
            f"entry_price={lot.entry_price:.2f} "
            f"qty_open={lot.qty_open} "
            f"unrealized_pnl={lot.unrealized_pnl:.2f} "
            f"mfe={lot.mfe:.2f} "
            f"mae={lot.mae:.2f}"
        )


def print_closed_trades(tracker: PositionTrackerEngine) -> None:
    trades = tracker.get_closed_trades()

    print("\nClosed Trades:")
    if not trades:
        print("  <none>")
        return

    for t in trades:
        print(
            f"  trade_id={t.trade_id} "
            f"lot_id={t.lot_id} "
            f"entry={t.entry_time} @{t.entry_price:.2f} "
            f"exit={t.exit_time} @{t.exit_price:.2f} "
            f"qty={t.qty} "
            f"pnl={t.pnl:.2f} "
            f"exit_action={t.exit_action}"
        )


def run_demo() -> None:
    tracker = PositionTrackerEngine(
        symbol="DEMO",
        initial_cash=100000.0,
        recent_window=10,
        recent_reduce_window=10,
        recent_sell_window=10,
    )

    print_header("STEP 0 - INITIAL")
    tracker.on_bar("2026-01-01 09:30:00", 10.00)
    print_snapshot(tracker, "initial")
    print_open_lots(tracker)

    print_header("STEP 1 - BUY FIRST LOT")
    tracker.on_buy(
        timestamp="2026-01-01 09:35:00",
        qty=200,
        price=10.00,
        entry_reason="alpha_buy",
        entry_signal="buy",
        entry_regime="trend",
        entry_atr=0.30,
    )
    tracker.on_bar("2026-01-01 09:35:00", 10.00)
    print_snapshot(tracker, "after first buy")
    print_open_lots(tracker)

    print_header("STEP 2 - PRICE UP")
    tracker.on_bar("2026-01-01 10:00:00", 10.50)
    print_snapshot(tracker, "after mark up")
    print_open_lots(tracker)

    print_header("STEP 3 - BUY SECOND LOT")
    tracker.on_buy(
        timestamp="2026-01-01 10:05:00",
        qty=100,
        price=10.60,
        entry_reason="add_buy",
        entry_signal="buy",
        entry_regime="trend",
        entry_atr=0.32,
    )
    tracker.on_bar("2026-01-01 10:05:00", 10.60)
    print_snapshot(tracker, "after second buy")
    print_open_lots(tracker)

    print_header("STEP 4 - PRICE DOWN")
    tracker.on_bar("2026-01-01 10:30:00", 9.80)
    print_snapshot(tracker, "after drawdown")
    print_open_lots(tracker)

    print_header("STEP 5 - REDUCE 150 (FIFO)")
    tracker.on_reduce(
        timestamp="2026-01-01 10:35:00",
        qty=150,
        price=10.20,
        exit_reason="alpha_reduce",
        exit_regime="range",
    )
    tracker.on_bar("2026-01-01 10:35:00", 10.20)
    print_snapshot(tracker, "after reduce")
    print_open_lots(tracker)
    print_closed_trades(tracker)

    print_header("STEP 6 - SELL 100 (FIFO)")
    tracker.on_sell(
        timestamp="2026-01-01 11:00:00",
        qty=100,
        price=10.90,
        exit_reason="alpha_sell",
        exit_regime="trend_late",
    )
    tracker.on_bar("2026-01-01 11:00:00", 10.90)
    print_snapshot(tracker, "after sell")
    print_open_lots(tracker)
    print_closed_trades(tracker)

    print_header("STEP 7 - FORCE EXIT REMAINING")
    tracker.on_force_exit(
        timestamp="2026-01-01 11:30:00",
        price=9.50,
        exit_reason="risk_force_exit",
        exit_regime="risk_high",
    )
    tracker.on_bar("2026-01-01 11:30:00", 9.50)
    print_snapshot(tracker, "after force exit")
    print_open_lots(tracker)
    print_closed_trades(tracker)

    print_header("STEP 8 - BASIC ASSERTIONS")
    snap = tracker.get_snapshot()

    assert snap.current_position_qty == 0, "Position should be fully closed"
    assert snap.open_lot_count == 0, "No open lots should remain"
    assert snap.closed_trade_count > 0, "Closed trades should exist"
    assert snap.equity_peak >= snap.equity, "Equity peak should be >= current equity"
    assert snap.max_drawdown <= 0, "Max drawdown should be <= 0"

    print("All assertions passed.")


if __name__ == "__main__":
    run_demo()