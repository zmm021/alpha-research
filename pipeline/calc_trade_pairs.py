from __future__ import annotations

import pandas as pd

INPUT_FILE = "results.csv"
START_DATE = "2025-07-01"


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


def load_results(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "datetime" not in df.columns:
        raise ValueError("results.csv must contain 'datetime' column")

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    return df


def build_trade_pairs(df: pd.DataFrame) -> list[dict]:
    inventory = []
    pairs = []

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

        if action == "buy":
            inventory.append(
                {
                    "price": price,
                    "qty": delta,
                    "datetime": row["datetime"],
                }
            )

        elif action in {"sell", "reduce"}:
            remaining = abs(delta)

            while remaining > 0 and inventory:
                lot = inventory[0]
                match_qty = min(lot["qty"], remaining)

                pnl = (price - lot["price"]) * match_qty

                pairs.append(
                    {
                        "entry_time": lot["datetime"],
                        "exit_time": row["datetime"],
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


def print_analysis(pairs: list[dict]) -> None:
    if not pairs:
        print("No trades found.")
        return

    df = pd.DataFrame(pairs)

    print("\n========== SAMPLE TRADE PAIRS (first 20) ==========")
    print(df.head(20).to_string(index=False))

    total_trades = len(df)
    total_pnl = df["pnl"].sum()

    win_trades = df[df["pnl"] > 0]
    loss_trades = df[df["pnl"] < 0]

    win_rate = len(win_trades) / total_trades if total_trades > 0 else 0.0

    avg_win = win_trades["pnl"].mean() if not win_trades.empty else 0.0
    avg_loss = loss_trades["pnl"].mean() if not loss_trades.empty else 0.0

    max_win = df["pnl"].max()
    max_loss = df["pnl"].min()

    print("\n========== OVERALL ==========")
    print(f"Total Trade Pairs: {total_trades}")
    print(f"Total PnL:         {total_pnl:.2f}")
    print(f"Win Rate:          {win_rate:.2%}")
    print(f"Avg Win:           {avg_win:.2f}")
    print(f"Avg Loss:          {avg_loss:.2f}")
    print(f"Max Win:           {max_win:.2f}")
    print(f"Max Loss:          {max_loss:.2f}")

    print("\nPnL Quantiles:")
    print(df["pnl"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_string())

    print("\n========== BY ACTION ==========")
    for action in ["sell", "reduce"]:
        sub = df[df["action"] == action]
        if sub.empty:
            continue

        action_win_rate = (sub["pnl"] > 0).mean()

        print(f"\n--- {action.upper()} ---")
        print(f"Trade Pairs: {len(sub)}")
        print(f"Total PnL:   {sub['pnl'].sum():.2f}")
        print(f"Win Rate:    {action_win_rate:.2%}")
        print(f"Avg PnL:     {sub['pnl'].mean():.2f}")
        print(f"Median PnL:  {sub['pnl'].median():.2f}")
        print(f"Max Win:     {sub['pnl'].max():.2f}")
        print(f"Max Loss:    {sub['pnl'].min():.2f}")


def main() -> None:
    df = load_results(INPUT_FILE)

    df = df[df["datetime"] >= START_DATE].copy()

    pairs = build_trade_pairs(df)
    print_analysis(pairs)


if __name__ == "__main__":
    main()