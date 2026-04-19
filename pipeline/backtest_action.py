from __future__ import annotations

import argparse
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
    logger.info("========== Start backtest action experiment ==========")
    logger.info(
        "Inputs | symbol=%s sector=%s start=%s end=%s symbol_freq=%s sector_freq=%s macro_freq=%s strict=%s",
        symbol,
        sector,
        start_date,
        end_date,
        symbol_freq,
        sector_freq,
        macro_freq,
        strict,
    )

    config_bundle = _load_config_bundle(config_dir)

    symbol_target_freq = _parse_bar_frequency(symbol_freq)
    sector_target_freq = _parse_bar_frequency(sector_freq)
    macro_target_freq = _parse_bar_frequency(macro_freq)

    logger.info("Parsed frequencies successfully")

    # =========================
    # 1. Load Data
    # =========================
    logger.info("Loading symbol bars...")
    symbol_df = load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        target_freq=symbol_target_freq,
        strict=False,
    )
    _log_df("symbol_df", symbol_df)

    logger.info("Loading sector bars...")
    sector_member_dfs = load_sector_bars(
        base_path=base_path,
        sector_name=sector,
        start_date=start_date,
        end_date=end_date,
        target_freq=sector_target_freq,
        strict=False,
    )
    logger.info("sector_member_dfs loaded | symbols=%s", list(sector_member_dfs.keys()))

    logger.info("Resolving sector ETF proxy...")
    sector_etf_df = _resolve_sector_etf_df(sector_member_dfs, sector_etf=sector_etf)
    _log_df("sector_etf_df", sector_etf_df)

    logger.info("Loading macro bars...")
    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_date,
        end_date=end_date,
        target_freq=macro_target_freq,
        strict=False,
    )
    logger.info("macro_data loaded | symbols=%s", list(macro_data.keys()))

    logger.info("Resolving macro inputs...")
    spy_df, vix_df, hy_oas_df = _resolve_macro_inputs(macro_data)
    _log_df("spy_df", spy_df)
    _log_df("vix_df", vix_df)
    _log_df("hy_oas_df", hy_oas_df)

    # =========================
    # 2. Build Features
    # =========================
    logger.info("Building feature frame...")
    feature_df = build_feature_frame(
        symbol_df=symbol_df,
        sector_etf_df=sector_etf_df,
        sector_member_dfs=sector_member_dfs,
        spy_df=spy_df,
        vix_df=vix_df,
        hy_oas_df=hy_oas_df,
        config_bundle=config_bundle,
    )
    _log_df("feature_df", feature_df)

    # =========================
    # 3. Compute Action Signals
    # =========================
    logger.info("Computing action signals...")
    action_signals = compute_action_signals(feature_df, config_bundle["signal"])
    logger.info("Action signals computed | count=%s", len(action_signals))

    action_df = feature_df.copy()
    action_df["action_signal"] = action_signals
    # position engine 需要 close
    if "close" not in action_df.columns:
        logger.info("close not found in action_df, joining close from symbol_df...")
        action_df = symbol_df[["close"]].join(action_df, how="left")
    # =========================
    # 4. Compute Position Actions
    # =========================
    logger.info("Computing position engine frame...")
    position_df = compute_position_engine_frame(action_df)
    _log_df("position_df", position_df)

    # =========================
    # 5. Merge All Outputs
    # =========================
    logger.info("Merging action + position outputs into feature frame...")
    final_df = action_df.join(position_df, how="left")

    logger.info("Joining original symbol bars back into final frame...")
    final_df = symbol_df.join(final_df, how="left", rsuffix="_feature")
    final_df = final_df.sort_index()
    _log_df("final_df", final_df)

    # =========================
    # 6. Export CSV
    # =========================
    if out_path is None:
        out_path = _build_default_output_path(symbol, start_date, end_date)

    logger.info("Exporting final dataframe to CSV: %s", out_path)
    final_df = final_df.drop(columns=["action_signal"], errors="ignore")
    export_dataframe_to_csv(final_df, out_path)
    logger.info("CSV export completed")

    logger.info("========== Backtest action experiment finished ==========")
    return final_df


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