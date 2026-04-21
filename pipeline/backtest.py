from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import yaml

from quant.engine.feature_engine import build_feature_frame
from quant.engine.signal_engine import compute_action_signals 
from quant.engine.tracker import PositionTrackerEngine
from quant.engine.decision_context import DecisionContextBuilder
from quant.engine.position_engine import PositionEngine
from quant.engine.decision_engine import DecisionEngine
from utils.bar_utls import BarFrequency
from utils.parquet_loader import (
    load_macro_bars,
    load_sector_bars,
    load_symbol_bars,
)
from utils.parquet_to_csv import export_dataframe_to_csv


DEFAULT_BASE_PATH = "data/market"
DEFAULT_CONFIG_DIR = "quant/config"

DEFAULT_SYMBOL_FREQ = "15min"
DEFAULT_SECTOR_FREQ = "1d"
DEFAULT_MACRO_FREQ = "1d"

EXPERIMENT_DIR = Path(__file__).resolve().parent


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


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
    logger.info("Resolving macro inputs from loaded macro symbols: %s", list(macro_data.keys()))

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
            raise ValueError(f"Requested sector ETF proxy {sector_etf} not found in loaded sector data")
        logger.info("Using explicit sector ETF proxy: %s", sector_etf)
        return sector_member_dfs[sector_etf]

    candidates = ["URNM", "URA", "REMX", "XLE", "SMH"]
    for etf_symbol in candidates:
        if etf_symbol in sector_member_dfs:
            logger.info("Using auto-detected sector ETF proxy: %s", etf_symbol)
            return sector_member_dfs[etf_symbol]

    raise ValueError(
        "No sector ETF proxy found. Please pass --sector-etf explicitly "
        "or add ETF proxy into the sector universe."
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


def _build_default_output_path(symbol: str, start_date: str, end_date: str) -> Path:
    safe_start = start_date.replace("-", "")
    safe_end = end_date.replace("-", "")
    # file_name = f"{symbol}_backtest_action_{safe_start}_{safe_end}.csv"
    file_name = "results.csv"
    return EXPERIMENT_DIR / file_name

def run_backtest_action_pipeline(
    *,
    symbol: str,
    sector: str,
    start_date: str,
    end_date: str,
    sector_etf: str | None = None,
    base_path: str | Path = DEFAULT_BASE_PATH,
    config_dir: str | Path = DEFAULT_CONFIG_DIR,
    symbol_freq: str = DEFAULT_SYMBOL_FREQ,
    sector_freq: str = DEFAULT_SECTOR_FREQ,
    macro_freq: str = DEFAULT_MACRO_FREQ,
    strict: bool = True,
    out_path: str | Path | None = None,
) -> pd.DataFrame: 

    TRADE_START_DATE = pd.Timestamp("2025-09-01", tz="UTC")

    logger.info("========== Start NEW backtest ==========")

    config_bundle = _load_config_bundle(config_dir)

    symbol_df = load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        target_freq=_parse_bar_frequency(symbol_freq),
        strict=False,
    )

    sector_member_dfs = load_sector_bars(
        base_path=base_path,
        sector_name=sector,
        start_date=start_date,
        end_date=end_date,
        target_freq=_parse_bar_frequency(sector_freq),
        strict=False,
    )

    sector_etf_df = _resolve_sector_etf_df(sector_member_dfs, sector_etf)

    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_date,
        end_date=end_date,
        target_freq=_parse_bar_frequency(macro_freq),
        strict=False,
    )

    spy_df, vix_df, hy_oas_df = _resolve_macro_inputs(macro_data)

    # =========================
    # Features
    # =========================
    feature_df = build_feature_frame(
        symbol_df=symbol_df,
        sector_etf_df=sector_etf_df,
        sector_member_dfs=sector_member_dfs,
        spy_df=spy_df,
        vix_df=vix_df,
        hy_oas_df=hy_oas_df,
        config_bundle=config_bundle,
    )

    # =========================
    # Signals
    # =========================
    signals = compute_action_signals(feature_df, config_bundle["signal"])

    df = feature_df.copy()
    df["action_signal"] = signals

    if "close" not in df.columns:
        df = symbol_df[["close"]].join(df, how="left")

    # =========================
    # NEW ENGINE LOOP
    # =========================
    tracker = PositionTrackerEngine(symbol=symbol)
    ctx_builder = DecisionContextBuilder()
    position_engine = PositionEngine()
    decision_engine = DecisionEngine()

    records = []

    for ts, row in df.iterrows():
        price = float(row["close"])

        tracker.on_bar(ts, price)

        snapshot = tracker.get_snapshot()
        ctx = ctx_builder.build(
            symbol=symbol,
            timestamp=ts,
            price=price,
            alpha_signal=row["action_signal"],
            symbol_state=row.get("symbol_state", "unknown"),
            sector_state=row.get("sector_state_sector", ""),
            macro_state=row.get("macro_state_macro", ""),
            range_position=row.get("symbol_range_position"),
            trend_slope=row.get("symbol_trend_slope_raw"),
            long_slope=row.get("symbol_long_slope_raw"),
            tracker_snapshot=snapshot,
        )
 
        proposal = position_engine.propose(ctx)
        decision = decision_engine.decide(ctx, proposal, base_qty=100)
 
        executed = False

        if ts >= TRADE_START_DATE:
            if decision.action == "buy" and decision.qty > 0:
                tracker.on_buy(ts, decision.qty, price)
                executed = True

            elif decision.action == "reduce" and decision.qty > 0:
                tracker.on_reduce(ts, decision.qty, price)
                executed = True

            elif decision.action == "sell" and decision.qty > 0:
                tracker.on_sell(ts, decision.qty, price)
                executed = True

            elif decision.action == "force_exit":
                tracker.on_force_exit(ts, price)
                executed = True

        snap = tracker.get_snapshot()

        records.append({
            "datetime": ts,
            "price": price,
            "signal": row["action_signal"],
            "proposal": proposal.action,
            "proposal_reason": proposal.reason,
            "decision": decision.action,
            "decision_reason": decision.reason,
            "qty": decision.qty,
            "executed": executed,
            "equity": snap.equity,
            "pnl": snap.realized_pnl_total,
            "drawdown": snap.current_drawdown,
        })

    result_df = pd.DataFrame(records).set_index("datetime")
     
    buy_df = result_df[
        (result_df.index >= TRADE_START_DATE) &
        (result_df["decision"] == "buy")
    ]
    # =========================
    # 🔥 PRINT STATS（核心）
    # =========================
    print("\n========== SIGNAL COUNTS ==========")
    print(df["action_signal"].astype(str).value_counts())

    trade_df = df[df.index >= TRADE_START_DATE].copy()
    print("\n========== SIGNAL COUNTS AFTER TRADE START ==========")
    print(trade_df["action_signal"].astype(str).value_counts())

    print("\n========== DECISION COUNTS ==========")
    print(result_df["decision"].value_counts())

    print("\n========== EXECUTED COUNTS ==========")
    print(result_df[result_df["executed"] == True]["decision"].value_counts())
    print("\n========== BACKTEST SUMMARY ==========")

    trades = tracker.get_closed_trades()

    if trades:
        pnl_list = [t.pnl for t in trades]

        total_pnl = sum(pnl_list)
        win = [p for p in pnl_list if p > 0]
        loss = [p for p in pnl_list if p < 0]

        print(f"Total Trades: {len(pnl_list)}")
        print(f"Total PnL:   {total_pnl:.2f}")
        print(f"Win Rate:    {len(win)/len(pnl_list):.2%}")
        print(f"Avg Win:     {sum(win)/len(win) if win else 0:.2f}")
        print(f"Avg Loss:    {sum(loss)/len(loss) if loss else 0:.2f}")
        print(f"Max Win:     {max(pnl_list):.2f}")
        print(f"Max Loss:    {min(pnl_list):.2f}")

    snap = tracker.get_snapshot()

    print("\n========== DRAWDOWN ==========")
    print(f"Final Equity: {snap.equity:.2f}")
    print(f"Max DD:       {snap.max_drawdown:.2f}")

    # =========================
    # EXPORT
    # =========================
    if out_path:
        export_dataframe_to_csv(result_df, out_path)

    return result_df
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline backtest action pipeline")

    parser.add_argument("--symbol", required=True, help="Target symbol, e.g. UUUU")
    parser.add_argument("--sector", required=True, help="Sector name, e.g. rare_earth")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")

    parser.add_argument("--sector-etf", required=False, help="Explicit sector ETF proxy, e.g. URNM")

    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)

    parser.add_argument("--symbol-freq", default=DEFAULT_SYMBOL_FREQ, choices=["1min", "5min", "15min", "30min", "1h", "1d"])
    parser.add_argument("--sector-freq", default=DEFAULT_SECTOR_FREQ, choices=["1min", "5min", "15min", "30min", "1h", "1d"])
    parser.add_argument("--macro-freq", default=DEFAULT_MACRO_FREQ, choices=["1min", "5min", "15min", "30min", "1h", "1d"])

    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--out", required=False, help="Optional output csv path")

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    run_backtest_action_pipeline(
        symbol=args.symbol,
        sector=args.sector,
        start_date=args.start_date,
        end_date=args.end_date,
        sector_etf=args.sector_etf,
        base_path=args.base_path,
        config_dir=args.config_dir,
        symbol_freq=args.symbol_freq,
        sector_freq=args.sector_freq,
        macro_freq=args.macro_freq,
        strict=args.strict,
        out_path=args.out,
    )


if __name__ == "__main__":
    main()