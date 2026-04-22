# Position Tracker Engine

## Purpose

`tracker/` provides an in-memory position/account lifecycle tracker for the trading system.

It is **not** a signal engine and **not** a risk engine.

Its responsibility is to:

- track open lots
- match exits using FIFO
- compute realized / unrealized pnl
- maintain equity / drawdown
- expose recent trade performance stats
- provide account / strategy context to Position Engine and future Risk Engine

---

## Why this layer exists

Without a dedicated tracker, the Position Engine cannot answer questions like:

- which lot is being sold?
- was the sell a profitable exit or a failed trade?
- how many recent reduce trades are losing?
- what is the current rolling drawdown?
- is the strategy degrading?

This layer decouples:

- alpha generation
- risk control
- position/account state
- execution decisions

---

## Folder structure

```text
quant/engine/tracker/
    __init__.py
    models.py
    snapshot.py
    tracker_core.py
    tracker_engine.py
```

Main public entry
Use only:
``` python
from quant.engine.tracker import PositionTrackerEngine
```

Usage example
``` python
from quant.engine.tracker import PositionTrackerEngine

tracker = PositionTrackerEngine(
    symbol="UUUU",
    initial_cash=0.0,
    recent_window=20,
    recent_reduce_window=20,
    recent_sell_window=20,
)

# mark current bar
tracker.on_bar(timestamp=ts0, price=5.20)

# buy 200
tracker.on_buy(
    timestamp=ts1,
    qty=200,
    price=5.25,
    entry_reason="alpha_buy",
    entry_signal="buy",
    entry_regime="trend",
    entry_atr=0.18,
)

# next bar update
tracker.on_bar(timestamp=ts2, price=5.40)

# reduce 100
closed = tracker.on_reduce(
    timestamp=ts3,
    qty=100,
    price=5.50,
    exit_reason="alpha_reduce",
    exit_regime="range",
)

snapshot = tracker.get_snapshot()

print(snapshot.current_position_qty)
print(snapshot.avg_cost)
print(snapshot.realized_pnl_total)
print(snapshot.unrealized_pnl_total)
print(snapshot.current_drawdown)
print(snapshot.recent_reduce_stats.median_pnl)
```
Core write methods

on_bar(timestamp, price)

Updates mark-to-market for all open lots and refreshes:
	•	unrealized pnl
	•	equity
	•	drawdown

on_buy(...)

Creates a new PositionLot.

on_reduce(...)

FIFO matches lots and records ClosedTrade rows.

on_sell(...)

Same as reduce, but tagged as sell.

on_force_exit(...)

Closes all current open lots using FIFO.

⸻

Core read methods

get_snapshot()

Returns a TrackerSnapshot containing:
	•	equity / drawdown
	•	realized / unrealized pnl
	•	position qty / avg cost
	•	recent trade stats
	•	recent reduce stats
	•	recent sell stats

get_open_lots()

Returns current open lots.

get_closed_trades()

Returns all matched closed trades.

⸻

Intended next step

This tracker should feed:
	•	position_engine_v2
	•	risk_signal_engine
	•	decision_engine

Typical future rules:
	•	disable reduce if recent reduce median pnl < 0
	•	enter defensive mode if current drawdown breaches threshold
	•	force exit if a lot loses beyond ATR-based stop
	•	lower probe size after consecutive losses



## 7. 用法建议

你现在可以在 simulation / realtime simulation 里这样接：

```python
from quant.engine.tracker import PositionTrackerEngine

tracker = PositionTrackerEngine(symbol="CRML", initial_cash=0.0)

for ts, row in df.iterrows():
    price = float(row["close"])
    tracker.on_bar(timestamp=ts, price=price)

    # 这里先是假设已有 final_action / qty
    if final_action == "buy" and qty > 0:
        tracker.on_buy(
            timestamp=ts,
            qty=qty,
            price=price,
            entry_reason="alpha_buy",
            entry_signal="buy",
            entry_regime=str(row.get("symbol_state", "")),
            entry_atr=float(row.get("atr_pct", 0.0) or 0.0),
        )

    elif final_action == "reduce" and qty > 0:
        tracker.on_reduce(
            timestamp=ts,
            qty=qty,
            price=price,
            exit_reason="alpha_reduce",
            exit_regime=str(row.get("symbol_state", "")),
        )

    elif final_action == "sell" and qty > 0:
        tracker.on_sell(
            timestamp=ts,
            qty=qty,
            price=price,
            exit_reason="alpha_sell",
            exit_regime=str(row.get("symbol_state", "")),
        )

snapshot = tracker.get_snapshot()
print(snapshot.realized_pnl_total)
print(snapshot.current_drawdown)
print(snapshot.recent_reduce_stats.median_pnl)
```

8. 这版先不做的

为了先落地，这版我刻意没加：
	•	shadow tracker
	•	probe / probation
	•	lot-level ATR stop logic
	•	core_qty / tactical_qty 精细拆分
	•	regime drift score
	•	按 action/regime 的复杂归因

这些都可以在你把这个 tracker 接进 simulation 后再加。

⸻

9. 我对这版的建议

你先别急着直接做新的智能 position engine。
先把这个 tracker 接进去，然后在每个 bar 打印这几个：
	•	current_position_qty
	•	avg_cost
	•	realized_pnl_total
	•	unrealized_pnl_total
	•	current_drawdown
	•	recent_reduce_stats.median_pnl
	•	recent_reduce_stats.consecutive_losses

你会马上知道：

哪些行为在拖垮系统
