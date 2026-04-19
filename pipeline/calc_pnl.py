import pandas as pd


START_DATE = "2026-01-01"

# 最悲观执行模型
BUY_EXEC_MULTIPLIER = 1.001
SELL_EXEC_MULTIPLIER = 0.999


def compute_realized_pnl_and_capital_with_pessimistic_execution(
    csv_path: str = "results.csv",
) -> None:
    df = pd.read_csv(csv_path)

    # =========================
    # 1. 识别时间列
    # =========================
    time_col = None
    for col in ["date", "datetime", "timestamp"]:
        if col in df.columns:
            time_col = col
            break

    if time_col is None:
        raise ValueError(
            "No datetime column found (expect one of: date / datetime / timestamp)"
        )

    df[time_col] = pd.to_datetime(df[time_col])

    # 统一去掉时区，避免 tz-aware / naive 比较报错
    if hasattr(df[time_col].dt, "tz") and df[time_col].dt.tz is not None:
        df[time_col] = df[time_col].dt.tz_convert(None)

    df = df.sort_values(time_col).reset_index(drop=True)

    # =========================
    # 2. 校验字段
    # =========================
    required_cols = ["open", "position_action", "position_delta"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # =========================
    # 3. 下一根 bar open 作为基准执行价
    # =========================
    df["next_open"] = df["open"].shift(-1)
    df = df[df["next_open"].notna()].copy()

    if df.empty:
        print("No executable rows after applying next-bar-open execution.")
        return

    start_ts = pd.Timestamp(START_DATE)

    # =========================
    # 4. 全量 FIFO inventory
    # =========================
    # inventory 元素: [buy_price, qty]
    inventory: list[list[float | int]] = []

    # 全局资金流，用于参考整段历史资金峰值
    cash_flow_global = 0.0
    global_capital_peak = 0.0

    # 2026 区间统计
    total_realized_pnl_2026 = 0.0
    total_buy_value_2026 = 0.0
    total_sell_value_2026 = 0.0
    total_buy_qty_2026 = 0
    total_sell_qty_2026 = 0

    # 2026 初始带仓成本
    opening_inventory_cost_2026 = None

    # 2026 开始后的“新增资金占用”
    cash_flow_since_2026 = 0.0
    additional_capital_needed_2026 = 0.0

    crossed_into_2026 = False

    for _, row in df.iterrows():
        ts = row[time_col]
        action = str(row["position_action"]).lower()
        delta = int(row["position_delta"])
        next_open = float(row["next_open"])

        # 在第一次进入 2026 时，先锁定期初库存成本
        if (not crossed_into_2026) and ts >= start_ts:
            opening_inventory_cost_2026 = sum(
                float(price) * int(qty) for price, qty in inventory
            )
            crossed_into_2026 = True

        is_in_scope = ts >= start_ts

        # =========================
        # BUY
        # =========================
        if action == "buy" and delta > 0:
            qty = delta
            exec_price = next_open * BUY_EXEC_MULTIPLIER
            buy_value = exec_price * qty

            # 全量 inventory 更新
            inventory.append([exec_price, qty])

            # 全局资金占用
            cash_flow_global -= buy_value
            global_capital_peak = max(global_capital_peak, -cash_flow_global)

            # 只统计 2026+
            if is_in_scope:
                total_buy_qty_2026 += qty
                total_buy_value_2026 += buy_value

                cash_flow_since_2026 -= buy_value
                additional_capital_needed_2026 = max(
                    additional_capital_needed_2026,
                    -cash_flow_since_2026,
                )

        # =========================
        # SELL / REDUCE
        # =========================
        elif action in {"sell", "reduce"} and delta < 0:
            qty_to_sell = -delta
            exec_price = next_open * SELL_EXEC_MULTIPLIER
            sell_value = exec_price * qty_to_sell

            # 全局现金流
            cash_flow_global += sell_value

            if is_in_scope:
                total_sell_qty_2026 += qty_to_sell
                total_sell_value_2026 += sell_value

                cash_flow_since_2026 += sell_value

            remaining = qty_to_sell

            # FIFO 配对
            while remaining > 0 and inventory:
                buy_price, buy_qty = inventory[0]
                buy_qty = int(buy_qty)

                if buy_qty <= remaining:
                    matched_qty = buy_qty
                    pnl = (exec_price - float(buy_price)) * matched_qty

                    if is_in_scope:
                        total_realized_pnl_2026 += pnl

                    remaining -= matched_qty
                    inventory.pop(0)
                else:
                    matched_qty = remaining
                    pnl = (exec_price - float(buy_price)) * matched_qty

                    if is_in_scope:
                        total_realized_pnl_2026 += pnl

                    inventory[0][1] = buy_qty - matched_qty
                    remaining = 0

    # 如果整个数据都没到 2026，兜底
    if opening_inventory_cost_2026 is None:
        opening_inventory_cost_2026 = 0.0

    # 2026 结束时剩余仓位
    remaining_position_qty = sum(int(qty) for _, qty in inventory)
    remaining_cost_basis = sum(float(price) * int(qty) for price, qty in inventory)

    required_capital_2026 = opening_inventory_cost_2026 + additional_capital_needed_2026

    return_on_capital_2026 = (
        total_realized_pnl_2026 / required_capital_2026
        if required_capital_2026 > 0
        else 0.0
    )

    print("\n========== Trading Summary (>= 2026, pessimistic next-open execution) ==========")
    print(f"Opening Inventory Cost 2026:   {opening_inventory_cost_2026:.2f}")
    print(f"Additional Capital Needed:     {additional_capital_needed_2026:.2f}")
    print(f"Required Capital (>=2026):     {required_capital_2026:.2f}")
    print(f"Global Capital Peak:           {global_capital_peak:.2f}")
    print(f"Total Buy Qty (>=2026):        {total_buy_qty_2026}")
    print(f"Total Sell Qty (>=2026):       {total_sell_qty_2026}")
    print(f"Total Buy Value (>=2026):      {total_buy_value_2026:.2f}")
    print(f"Total Sell Value (>=2026):     {total_sell_value_2026:.2f}")
    print(f"Realized PnL (>=2026):         {total_realized_pnl_2026:.2f}")
    print(f"Return on Capital (>=2026):    {return_on_capital_2026:.2%}")
    print(f"Open Position Qty (end):       {remaining_position_qty}")
    print(f"Open Position Cost (end):      {remaining_cost_basis:.2f}")
    print("===============================================================================\n")


if __name__ == "__main__":
    compute_realized_pnl_and_capital_with_pessimistic_execution("results.csv")