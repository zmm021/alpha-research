from __future__ import annotations

import pandas as pd

INPUT_FILE = "results_uuuu.csv"
START_DATE = "2025-07-01"


# =========================
# Utils
# =========================
def _normalize_action(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if hasattr(value, "value"):
        return str(value.value).lower()

    s = str(value).strip().lower()
    if "." in s:
        s = s.split(".")[-1]

    return s


def _compute_max_drawdown(equity_series: pd.Series):
    if equity_series.empty:
        return 0.0, None, None

    running_peak = equity_series.cummax()
    drawdown = equity_series - running_peak
    max_drawdown = float(drawdown.min())

    if max_drawdown == 0.0:
        return 0.0, None, None

    trough_time = drawdown.idxmin()
    peak_time = equity_series.loc[:trough_time].idxmax()

    return max_drawdown, peak_time, trough_time


def _print_distribution_stats(name: str, series: pd.Series) -> None:
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        print(f"{name}: no data")
        return

    print(f"\n{name}:")
    print(f"Count:   {len(clean)}")
    print(f"Mean:    {clean.mean():.2f}")
    print(f"Std:     {clean.std():.2f}")
    print(f"Min:     {clean.min():.2f}")
    print(f"P10:     {clean.quantile(0.10):.2f}")
    print(f"P25:     {clean.quantile(0.25):.2f}")
    print(f"P50:     {clean.quantile(0.50):.2f}")
    print(f"P75:     {clean.quantile(0.75):.2f}")
    print(f"P90:     {clean.quantile(0.90):.2f}")
    print(f"Max:     {clean.max():.2f}")


# =========================
# Load
# =========================
def load_results(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    return df


# =========================
# FIFO + Filtered PnL
# =========================
def build_filtered_pairs(df: pd.DataFrame, start_date: str):
    inventory = []
    pairs = []

    start_ts = pd.Timestamp(start_date)

    # 和 df["datetime"] 对齐时区
    sample_ts = df["datetime"].iloc[0]
    if getattr(sample_ts, "tzinfo", None) is not None:
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize(sample_ts.tzinfo)
        else:
            start_ts = start_ts.tz_convert(sample_ts.tzinfo)

    for _, row in df.iterrows():
        action = _normalize_action(row["position_action"])

        try:
            delta = int(row["position_delta"] or 0)
        except Exception:
            delta = 0

        if delta == 0:
            continue

        price = row["executed_price"]
        if pd.isna(price):
            price = row["close"]

        price = float(price)
        ts = row["datetime"]

        # BUY → always 入库存
        if action == "buy":
            inventory.append(
                {
                    "price": price,
                    "qty": delta,
                    "datetime": ts,
                }
            )

        # SELL / REDUCE → FIFO
        elif action in {"sell", "reduce"}:
            remaining = abs(delta)

            while remaining > 0 and inventory:
                lot = inventory[0]
                match_qty = min(lot["qty"], remaining)

                entry_ts = lot["datetime"]
                exit_ts = ts
                pnl = (price - lot["price"]) * match_qty

                # 只统计 2026+ 新开仓并在 2026+ 平掉的部分
                if entry_ts >= start_ts and exit_ts >= start_ts:
                    pairs.append(
                        {
                            "entry_time": entry_ts,
                            "exit_time": exit_ts,
                            "action": action,
                            "qty": match_qty,
                            "entry_price": lot["price"],
                            "exit_price": price,
                            "pnl": pnl,
                        }
                    )

                lot["qty"] -= match_qty
                remaining -= match_qty

                if lot["qty"] == 0:
                    inventory.pop(0)

    return pairs


# =========================
# Analysis
# =========================
def print_analysis(pairs):
    if not pairs:
        print("No trades found.")
        return

    df = pd.DataFrame(pairs)
    df = df.sort_values("exit_time").reset_index(drop=True)

    # 累计 realized pnl 曲线
    df["equity_curve"] = df["pnl"].cumsum()

    # 最大回撤
    equity_series = df.set_index("exit_time")["equity_curve"]
    max_drawdown, peak_time, trough_time = _compute_max_drawdown(equity_series)

    print("\n========== SAMPLE (first 20) ==========")
    print(df.head(20).to_string(index=False))

    total_trades = len(df)
    total_pnl = df["pnl"].sum()

    win_trades = df[df["pnl"] > 0]
    loss_trades = df[df["pnl"] < 0]

    win_rate = len(win_trades) / total_trades if total_trades > 0 else 0.0

    avg_win = win_trades["pnl"].mean() if not win_trades.empty else 0.0
    avg_loss = loss_trades["pnl"].mean() if not loss_trades.empty else 0.0

    print("\n========== OVERALL (>= 2026 ONLY NEW TRADES) ==========")
    print(f"Total Trade Pairs: {total_trades}")
    print(f"Total PnL:         {total_pnl:.2f}")
    print(f"Win Rate:          {win_rate:.2%}")
    print(f"Avg Win:           {avg_win:.2f}")
    print(f"Avg Loss:          {avg_loss:.2f}")
    print(f"Max Win:           {df['pnl'].max():.2f}")
    print(f"Max Loss:          {df['pnl'].min():.2f}")

    print("\nPnL Quantiles:")
    print(df["pnl"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    print("\n========== DRAWDOWN ==========")
    print(f"Final Equity:      {df['equity_curve'].iloc[-1]:.2f}")
    print(f"Max Drawdown:      {max_drawdown:.2f}")
    print(f"Peak Time:         {peak_time}")
    print(f"Trough Time:       {trough_time}")

    _print_distribution_stats("Trade PnL Distribution", df["pnl"])
    _print_distribution_stats("Equity Distribution", df["equity_curve"])

    print("\n========== BY ACTION ==========")
    for action in ["sell", "reduce"]:
        sub = df[df["action"] == action]
        if sub.empty:
            continue

        action_win_rate = (sub["pnl"] > 0).mean()
        action_equity = sub["pnl"].cumsum()
        action_mdd, action_peak, action_trough = _compute_max_drawdown(
            pd.Series(action_equity.values, index=sub["exit_time"])
        )

        print(f"\n--- {action.upper()} ---")
        print(f"Trade Pairs: {len(sub)}")
        print(f"Total PnL:   {sub['pnl'].sum():.2f}")
        print(f"Win Rate:    {action_win_rate:.2%}")
        print(f"Avg PnL:     {sub['pnl'].mean():.2f}")
        print(f"Median PnL:  {sub['pnl'].median():.2f}")
        print(f"Max Win:     {sub['pnl'].max():.2f}")
        print(f"Max Loss:    {sub['pnl'].min():.2f}")
        print(f"Max DD:      {action_mdd:.2f}")
        print(f"DD Peak:     {action_peak}")
        print(f"DD Trough:   {action_trough}")


# =========================
# Main
# =========================
def main():
    df = load_results(INPUT_FILE)
    pairs = build_filtered_pairs(df, START_DATE)
    print_analysis(pairs)


if __name__ == "__main__":
    main()