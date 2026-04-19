from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yaml

from quant.engine.feature_engine import build_feature_frame
from quant.engine.signal_engine import compute_action_signals
from quant.engine.position_engine import compute_position_engine_frame
from utils.bar_utls import BarFrequency
from utils.parquet_loader import (
    load_macro_bars,
    load_sector_bars,
    load_symbol_bars,
)
from utils.parquet_to_csv import export_dataframe_to_csv


# =========================================================
# Simulation Parameters
# =========================================================
DEFAULT_BASE_PATH = "data/market"
DEFAULT_CONFIG_DIR = "quant/config"

SIM_SYMBOL = "UUUU"
SIM_SECTOR = "rare_earth"
SIM_SECTOR_ETF = "REMX"

SIM_START_DATE = "2025-01-01"
SIM_END_DATE = "2026-03-31"
COLD_START_END_DATE = "2025-06-30"

# 从这个日期开始记录 BUY / SELL / REDUCE cache
RECORD_START_DATE = "2025-07-01"

DEFAULT_SYMBOL_FREQ = "15min"
DEFAULT_SECTOR_FREQ = "1d"
DEFAULT_MACRO_FREQ = "1d"

OUTPUT_FILE_NAME = "simulation_results.csv"
SIMULATION_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)


# =========================================================
# Logging
# =========================================================
def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


# =========================================================
# Basic Helpers
# =========================================================
def _parse_bar_frequency(value: str) -> BarFrequency:
    mapping = {
        "1min": BarFrequency.MIN_1,
        "5min": BarFrequency.MIN_5,
        "15min": BarFrequency.MIN_15,
        "30min": BarFrequency.MIN_30,
        "1h": BarFrequency.HOUR_1,
        "1d": BarFrequency.DAY_1,
    }
    if value not in mapping:
        raise ValueError(f"Unsupported frequency: {value}")
    return mapping[value]


def _load_yaml(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_config_bundle(config_dir: str | Path) -> dict:
    config_dir = Path(config_dir)
    logger.info("Loading config bundle from %s", config_dir)

    bundle = {
        "macro": _load_yaml(config_dir / "macro.yaml"),
        "sector": _load_yaml(config_dir / "sector.yaml"),
        "symbol": _load_yaml(config_dir / "symbol.yaml"),
        "signal": _load_yaml(config_dir / "signal.yaml"),
    }

    logger.info("Config bundle loaded: %s", list(bundle.keys()))
    return bundle


def _resolve_macro_inputs(
    macro_data: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logger.info(
        "Resolving macro inputs from loaded macro symbols: %s",
        list(macro_data.keys()),
    )

    required = ["SPY", "VIX"]
    missing = [s for s in required if s not in macro_data]
    if missing:
        raise ValueError(f"Missing required macro symbols: {missing}")

    spy_df = macro_data["SPY"]
    vix_df = macro_data["VIX"]

    if "HY_OAS" in macro_data:
        hy_oas_df = macro_data["HY_OAS"]
        logger.info("Using HY_OAS as credit risk input")
    elif "TLT" in macro_data:
        hy_oas_df = macro_data["TLT"]
        logger.warning("HY_OAS not found, fallback to TLT as temporary proxy")
    else:
        raise ValueError("Missing HY_OAS and fallback TLT in macro data")

    return spy_df, vix_df, hy_oas_df


def _resolve_sector_etf_df(
    sector_member_dfs: dict[str, pd.DataFrame],
    sector_etf: str | None = None,
) -> pd.DataFrame:
    if sector_etf:
        if sector_etf not in sector_member_dfs:
            raise ValueError(
                f"Requested sector ETF proxy {sector_etf} not found in loaded sector data"
            )
        logger.info("Using explicit sector ETF proxy: %s", sector_etf)
        return sector_member_dfs[sector_etf]

    candidates = ["URNM", "URA", "REMX", "XLE", "SMH"]
    for etf_symbol in candidates:
        if etf_symbol in sector_member_dfs:
            logger.info("Using auto-detected sector ETF proxy: %s", etf_symbol)
            return sector_member_dfs[etf_symbol]

    raise ValueError(
        "No sector ETF proxy found. Please set SIM_SECTOR_ETF or add ETF proxy into sector universe."
    )


def _log_df(name: str, df: pd.DataFrame) -> None:
    logger.info(
        "%s loaded/computed | rows=%s cols=%s start=%s end=%s",
        name,
        len(df),
        len(df.columns),
        df.index.min() if isinstance(df.index, pd.DatetimeIndex) and not df.empty else "N/A",
        df.index.max() if isinstance(df.index, pd.DatetimeIndex) and not df.empty else "N/A",
    )


def _build_output_path() -> Path:
    return SIMULATION_DIR / OUTPUT_FILE_NAME


# =========================================================
# Time Helpers
# =========================================================
def _align_ts_to_index_tz(ts: pd.Timestamp, df: pd.DataFrame) -> pd.Timestamp:
    if getattr(df.index, "tz", None) is not None:
        if ts.tzinfo is None:
            return ts.tz_localize(df.index.tz)
        return ts.tz_convert(df.index.tz)
    return ts


def _split_cold_start(
    symbol_df: pd.DataFrame,
    cold_start_end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_ts = _align_ts_to_index_tz(pd.Timestamp(cold_start_end_date), symbol_df)

    history_df = symbol_df[symbol_df.index <= split_ts].copy()
    stream_df = symbol_df[symbol_df.index > split_ts].copy()

    return history_df, stream_df


def _slice_df_upto(df: pd.DataFrame, ts) -> pd.DataFrame:
    return df[df.index <= ts].copy()


def _slice_dict_upto(
    dfs: dict[str, pd.DataFrame],
    ts,
) -> dict[str, pd.DataFrame]:
    return {k: v[v.index <= ts].copy() for k, v in dfs.items()}


# =========================================================
# Action Normalizer
# =========================================================
def _normalize_action_value(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    # enum object with .value
    if hasattr(value, "value"):
        return str(value.value).lower()

    s = str(value).strip().lower()

    # handle strings like "ActionSignal.BUY"
    if "." in s:
        s = s.split(".")[-1]

    return s


# =========================================================
# Feature / Signal / Position Build
# =========================================================
def _build_full_state(
    *,
    symbol_df: pd.DataFrame,
    sector_etf_df: pd.DataFrame,
    sector_member_dfs: dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    hy_oas_df: pd.DataFrame,
    config_bundle: dict,
) -> pd.DataFrame:
    feature_df = build_feature_frame(
        symbol_df=symbol_df,
        sector_etf_df=sector_etf_df,
        sector_member_dfs=sector_member_dfs,
        spy_df=spy_df,
        vix_df=vix_df,
        hy_oas_df=hy_oas_df,
        config_bundle=config_bundle,
    )

    action_signals = compute_action_signals(feature_df, config_bundle["signal"])
    feature_df["action_signal"] = action_signals

    if "close" not in feature_df.columns:
        feature_df = symbol_df[["open", "high", "low", "close", "volume"]].join(
            feature_df,
            how="left",
        )

    position_df = compute_position_engine_frame(feature_df)
    full_df = feature_df.join(position_df, how="left")

    return full_df


def _extract_record_from_row(df: pd.DataFrame, idx: int) -> dict:
    row = df.iloc[idx]
    return {
        "datetime": df.index[idx],
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),
        "volume": row.get("volume"),
        "symbol_state": row.get("symbol_state"),
        "sector_state_sector": row.get("sector_state_sector"),
        "macro_state_macro": row.get("macro_state_macro"),
        "symbol_range_position": row.get("symbol_range_position"),
        "action_signal": row.get("action_signal"),
        "position_action": row.get("position_action"),
        "position_delta": row.get("position_delta"),
        "position_size": row.get("position_size"),
        "executed_price": row.get("executed_price"),
    }


# =========================================================
# Cache Builder
# =========================================================
def _build_action_caches_from_result_df(
    result_df: pd.DataFrame,
    record_start_ts,
) -> tuple[list[dict], list[dict], list[dict]]:
    if result_df.empty:
        return [], [], []

    df = result_df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df[df["datetime"] >= record_start_ts].copy()

    if df.empty:
        return [], [], []

    buy_cache: list[dict] = []
    sell_cache: list[dict] = []
    reduce_cache: list[dict] = []

    for _, row in df.iterrows():
        action = _normalize_action_value(row.get("position_action"))

        try:
            delta = int(row.get("position_delta", 0) or 0)
        except Exception:
            delta = 0

        if action not in {"buy", "sell", "reduce"} or delta == 0:
            continue

        exec_price = row.get("executed_price")
        if pd.isna(exec_price):
            exec_price = row.get("close", 0.0)

        try:
            exec_price = float(exec_price or 0.0)
        except Exception:
            exec_price = 0.0

        item = {
            "datetime": row.get("datetime"),
            "action": action,
            "qty": abs(delta),
            "price": exec_price,
        }

        if action == "buy":
            buy_cache.append(item)
        elif action == "sell":
            sell_cache.append(item)
        elif action == "reduce":
            reduce_cache.append(item)

    return buy_cache, sell_cache, reduce_cache


# =========================================================
# Cache Print
# =========================================================
def _format_cache_items(items: list[dict], max_items: int = 10) -> str:
    if not items:
        return "[]"

    sliced = items[-max_items:]
    parts = [
        f"{x['datetime']} | {x['action']} {x['qty']} @ {x['price']:.4f}"
        for x in sliced
    ]
    return "[\n  " + "\n  ".join(parts) + "\n]"


def _print_bar_cache_summary(
    latest_record: dict,
    buy_cache: list[dict],
    sell_cache: list[dict],
    reduce_cache: list[dict],
) -> None:
    dt = latest_record.get("datetime")
    close = latest_record.get("close", 0.0)
    symbol_state = latest_record.get("symbol_state")
    action_signal = _normalize_action_value(latest_record.get("action_signal"))
    position_action = _normalize_action_value(latest_record.get("position_action"))
    position_size = latest_record.get("position_size")

    try:
        close = float(close or 0.0)
    except Exception:
        close = 0.0

    print("\n============================================================")
    print(f"BAR: {dt}")
    print(f"Close: {close:.4f}")
    print(f"Symbol State: {symbol_state}")
    print(f"Action Signal: {action_signal}")
    print(f"Position Action: {position_action}")
    print(f"Position Size: {position_size}")
    print(f"Recorded Trades Since {RECORD_START_DATE}: {len(buy_cache) + len(sell_cache) + len(reduce_cache)}")
    print("")
    print(f"BUY Cache ({len(buy_cache)}):")
    print(_format_cache_items(buy_cache))
    print("")
    print(f"SELL Cache ({len(sell_cache)}):")
    print(_format_cache_items(sell_cache))
    print("")
    print(f"REDUCE Cache ({len(reduce_cache)}):")
    print(_format_cache_items(reduce_cache))
    print("============================================================")


# =========================================================
# Trade Ledger / Summary
# =========================================================
def _build_trade_ledger(result_df: pd.DataFrame, record_start_ts) -> pd.DataFrame:
    ledger_rows: list[dict] = []

    for _, row in result_df.iterrows():
        dt = row.get("datetime")
        if pd.isna(dt) or dt < record_start_ts:
            continue

        action = _normalize_action_value(row.get("position_action"))

        try:
            delta = int(row.get("position_delta", 0) or 0)
        except Exception:
            delta = 0

        if action not in {"buy", "sell", "reduce"} or delta == 0:
            continue

        exec_price = row.get("executed_price")
        if pd.isna(exec_price):
            exec_price = row.get("close", 0.0)

        try:
            exec_price = float(exec_price or 0.0)
        except Exception:
            exec_price = 0.0

        ledger_rows.append(
            {
                "datetime": dt,
                "action": action,
                "qty": abs(delta),
                "price": exec_price,
                "notional": abs(delta) * exec_price,
            }
        )

    return pd.DataFrame(
        ledger_rows,
        columns=["datetime", "action", "qty", "price", "notional"],
    )


def _compute_realized_pnl_from_ledger(ledger_df: pd.DataFrame) -> float:
    if ledger_df.empty:
        return 0.0

    inventory: list[list[float | int]] = []
    total_realized_pnl = 0.0

    for _, row in ledger_df.iterrows():
        action = _normalize_action_value(row["action"])
        qty = int(row["qty"])
        price = float(row["price"])

        if action == "buy":
            inventory.append([price, qty])

        elif action in {"sell", "reduce"}:
            remaining = qty

            while remaining > 0 and inventory:
                buy_price, buy_qty = inventory[0]
                buy_qty = int(buy_qty)

                if buy_qty <= remaining:
                    matched_qty = buy_qty
                    total_realized_pnl += (price - float(buy_price)) * matched_qty
                    remaining -= matched_qty
                    inventory.pop(0)
                else:
                    matched_qty = remaining
                    total_realized_pnl += (price - float(buy_price)) * matched_qty
                    inventory[0][1] = buy_qty - matched_qty
                    remaining = 0

    return total_realized_pnl


def _print_simulation_summary(
    result_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    record_start_ts,
) -> None:
    if result_df.empty:
        logger.info("Simulation result is empty.")
        return

    if ledger_df.empty:
        total_trade_count = 0
        buy_count = 0
        sell_count = 0
        reduce_count = 0
        realized_pnl = 0.0
    else:
        total_trade_count = len(ledger_df)
        buy_count = len(ledger_df[ledger_df["action"] == "buy"])
        sell_count = len(ledger_df[ledger_df["action"] == "sell"])
        reduce_count = len(ledger_df[ledger_df["action"] == "reduce"])
        realized_pnl = _compute_realized_pnl_from_ledger(ledger_df)

    scoped_df = result_df[result_df["datetime"] >= record_start_ts].copy()
    if scoped_df.empty:
        scoped_df = result_df.copy()

    max_position_size = 0
    max_position_value = 0.0

    for _, row in scoped_df.iterrows():
        try:
            position_size = int(row.get("position_size", 0) or 0)
        except Exception:
            position_size = 0

        try:
            close_price = float(row.get("close", 0.0) or 0.0)
        except Exception:
            close_price = 0.0

        position_value = position_size * close_price

        if position_size > max_position_size:
            max_position_size = position_size

        if position_value > max_position_value:
            max_position_value = position_value

    print("\n========== Simulation Summary ==========")
    print(f"Symbol:                 {SIM_SYMBOL}")
    print(f"Window:                 {SIM_START_DATE} -> {SIM_END_DATE}")
    print(f"Cold Start End:         {COLD_START_END_DATE}")
    print(f"Record Start:           {RECORD_START_DATE}")
    print(f"Total Trade Count:      {total_trade_count}")
    print(f"BUY Count:              {buy_count}")
    print(f"SELL Count:             {sell_count}")
    print(f"REDUCE Count:           {reduce_count}")
    print(f"Max Position Size:      {max_position_size}")
    print(f"Max Position Value:     {max_position_value:.2f}")
    print(f"Realized PnL (FIFO):    {realized_pnl:.2f}")
    print("========================================\n")


# =========================================================
# Main Simulation
# =========================================================
def run_realtime_simulation() -> pd.DataFrame:
    logger.info("========== Start realtime simulation ==========")
    logger.info(
        "Params | symbol=%s sector=%s sector_etf=%s start=%s end=%s cold_start_end=%s "
        "record_start=%s symbol_freq=%s sector_freq=%s macro_freq=%s",
        SIM_SYMBOL,
        SIM_SECTOR,
        SIM_SECTOR_ETF,
        SIM_START_DATE,
        SIM_END_DATE,
        COLD_START_END_DATE,
        RECORD_START_DATE,
        DEFAULT_SYMBOL_FREQ,
        DEFAULT_SECTOR_FREQ,
        DEFAULT_MACRO_FREQ,
    )

    config_bundle = _load_config_bundle(DEFAULT_CONFIG_DIR)

    symbol_target_freq = _parse_bar_frequency(DEFAULT_SYMBOL_FREQ)
    sector_target_freq = _parse_bar_frequency(DEFAULT_SECTOR_FREQ)
    macro_target_freq = _parse_bar_frequency(DEFAULT_MACRO_FREQ)

    logger.info("Loading symbol bars...")
    symbol_df = load_symbol_bars(
        base_path=DEFAULT_BASE_PATH,
        symbol=SIM_SYMBOL,
        start_date=SIM_START_DATE,
        end_date=SIM_END_DATE,
        target_freq=symbol_target_freq,
        strict=False,
    )
    _log_df("symbol_df", symbol_df)

    record_start_ts = _align_ts_to_index_tz(pd.Timestamp(RECORD_START_DATE), symbol_df)

    logger.info("Loading sector bars...")
    sector_member_dfs_full = load_sector_bars(
        base_path=DEFAULT_BASE_PATH,
        sector_name=SIM_SECTOR,
        start_date=SIM_START_DATE,
        end_date=SIM_END_DATE,
        target_freq=sector_target_freq,
        strict=False,
    )
    logger.info(
        "sector_member_dfs_full loaded | symbols=%s",
        list(sector_member_dfs_full.keys()),
    )

    logger.info("Resolving sector ETF proxy...")
    sector_etf_df_full = _resolve_sector_etf_df(
        sector_member_dfs=sector_member_dfs_full,
        sector_etf=SIM_SECTOR_ETF,
    )
    _log_df("sector_etf_df_full", sector_etf_df_full)

    logger.info("Loading macro bars...")
    macro_data_full = load_macro_bars(
        base_path=DEFAULT_BASE_PATH,
        start_date=SIM_START_DATE,
        end_date=SIM_END_DATE,
        target_freq=macro_target_freq,
        strict=False,
    )
    logger.info("macro_data_full loaded | symbols=%s", list(macro_data_full.keys()))

    logger.info("Resolving macro inputs...")
    spy_df_full, vix_df_full, hy_oas_df_full = _resolve_macro_inputs(macro_data_full)
    _log_df("spy_df_full", spy_df_full)
    _log_df("vix_df_full", vix_df_full)
    _log_df("hy_oas_df_full", hy_oas_df_full)

    history_df, stream_df = _split_cold_start(symbol_df, COLD_START_END_DATE)

    if history_df.empty:
        raise ValueError("Cold start history is empty.")
    if stream_df.empty:
        raise ValueError("Streaming window is empty.")

    _log_df("history_df", history_df)
    _log_df("stream_df", stream_df)

    cold_end_ts = history_df.index.max()

    logger.info("Building cold start state with point-in-time sliced inputs...")
    current_symbol_df = history_df.copy()
    current_sector_etf_df = _slice_df_upto(sector_etf_df_full, cold_end_ts)
    current_sector_member_dfs = _slice_dict_upto(sector_member_dfs_full, cold_end_ts)
    current_spy_df = _slice_df_upto(spy_df_full, cold_end_ts)
    current_vix_df = _slice_df_upto(vix_df_full, cold_end_ts)
    current_hy_oas_df = _slice_df_upto(hy_oas_df_full, cold_end_ts)

    full_state_df = _build_full_state(
        symbol_df=current_symbol_df,
        sector_etf_df=current_sector_etf_df,
        sector_member_dfs=current_sector_member_dfs,
        spy_df=current_spy_df,
        vix_df=current_vix_df,
        hy_oas_df=current_hy_oas_df,
        config_bundle=config_bundle,
    )
    _log_df("cold_start_full_state_df", full_state_df)

    records: list[dict] = []
    for idx in range(len(full_state_df)):
        records.append(_extract_record_from_row(full_state_df, idx))

    logger.info("Cold start completed. Start streaming replay...")

    for ts, new_row in stream_df.iterrows():
        current_symbol_df.loc[ts] = new_row

        current_sector_etf_df = _slice_df_upto(sector_etf_df_full, ts)
        current_sector_member_dfs = _slice_dict_upto(sector_member_dfs_full, ts)
        current_spy_df = _slice_df_upto(spy_df_full, ts)
        current_vix_df = _slice_df_upto(vix_df_full, ts)
        current_hy_oas_df = _slice_df_upto(hy_oas_df_full, ts)

        full_state_df = _build_full_state(
            symbol_df=current_symbol_df,
            sector_etf_df=current_sector_etf_df,
            sector_member_dfs=current_sector_member_dfs,
            spy_df=current_spy_df,
            vix_df=current_vix_df,
            hy_oas_df=current_hy_oas_df,
            config_bundle=config_bundle,
        )

        latest_record = _extract_record_from_row(full_state_df, len(full_state_df) - 1)
        records.append(latest_record)

        current_result_df = pd.DataFrame(records)
        current_result_df["datetime"] = pd.to_datetime(current_result_df["datetime"])
        current_result_df = current_result_df.sort_values("datetime").reset_index(drop=True)

        buy_cache, sell_cache, reduce_cache = _build_action_caches_from_result_df(
            current_result_df,
            record_start_ts=record_start_ts,
        )

        _print_bar_cache_summary(
            latest_record=latest_record,
            buy_cache=buy_cache,
            sell_cache=sell_cache,
            reduce_cache=reduce_cache,
        )

    result_df = pd.DataFrame(records)
    result_df["datetime"] = pd.to_datetime(result_df["datetime"])
    result_df = result_df.sort_values("datetime").reset_index(drop=True)

    out_path = _build_output_path()
    logger.info("Exporting simulation results to CSV: %s", out_path)
    export_dataframe_to_csv(result_df, out_path)

    ledger_df = _build_trade_ledger(result_df, record_start_ts=record_start_ts)
    _print_simulation_summary(
        result_df=result_df,
        ledger_df=ledger_df,
        record_start_ts=record_start_ts,
    )

    logger.info("Simulation completed | total_rows=%s", len(result_df))
    logger.info("========== Realtime simulation finished ==========")

    return result_df


def main() -> None:
    setup_logging()
    run_realtime_simulation()


if __name__ == "__main__":
    main()