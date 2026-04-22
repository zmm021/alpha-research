from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import pandas as pd
import yaml

from utils.bar_utls import BarFrequency
from utils.parquet_loader import (
    load_macro_bars,
    load_sector_bars,
    load_symbol_bars,
)

from quant.engine.feature_engine import build_feature_frame
from quant.macro.macro_engine import MacroEngine
from quant.sector.sector_engine import SectorEngine
from quant.symbol.symbol_engine import SymbolEngine


DEFAULT_BASE_PATH = "data/market"
DEFAULT_CONFIG_DIR = "quant/config"
DEFAULT_OUTPUT_DETAIL = "pipeline/validation_columns_detail.csv"
DEFAULT_OUTPUT_SUMMARY = "pipeline/validation_columns_summary.csv"

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


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=True)
    return out.sort_index()


def _log_df(name: str, df: pd.DataFrame) -> None:
    logger.info(
        "%s | rows=%s cols=%s start=%s end=%s",
        name,
        len(df),
        len(df.columns),
        df.index.min() if isinstance(df.index, pd.DatetimeIndex) and not df.empty else "N/A",
        df.index.max() if isinstance(df.index, pd.DatetimeIndex) and not df.empty else "N/A",
    )


def _safe_member_close_frame(
    sector_member_dfs: Dict[str, pd.DataFrame],
    target_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    frames = []
    for ticker, df in (sector_member_dfs or {}).items():
        if df is None or df.empty or "close" not in df.columns:
            continue
        tmp = _ensure_datetime_index(df)[["close"]].rename(columns={"close": ticker})
        tmp = tmp.reindex(target_index)
        frames.append(tmp)

    if not frames:
        return pd.DataFrame(index=target_index.copy())

    return pd.concat(frames, axis=1).sort_index()


def _get_prev_close(df: pd.DataFrame, ts: pd.Timestamp) -> float | None:
    if df is None or df.empty or ts not in df.index:
        return None

    loc = df.index.get_loc(ts)
    if isinstance(loc, slice):
        return None
    if loc <= 0:
        return None

    try:
        return float(df.iloc[loc - 1]["close"])
    except Exception:
        return None


def _build_symbol_bar(symbol_df: pd.DataFrame, ts: pd.Timestamp) -> Dict[str, Any]:
    row = symbol_df.loc[ts]
    return {
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
    }


def _build_sector_bar(sector_etf_df: pd.DataFrame, ts: pd.Timestamp) -> Dict[str, Any]:
    row = sector_etf_df.loc[ts]
    return {
        "open": float(row.get("open", row["close"])),
        "high": float(row.get("high", row["close"])),
        "low": float(row.get("low", row["close"])),
        "close": float(row["close"]),
        "volume": float(row.get("volume", 0.0)),
    }


def _build_macro_bar(
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    hy_oas_df: pd.DataFrame,
    ts: pd.Timestamp,
) -> Dict[str, Any]:
    spy_row = spy_df.loc[ts]
    vix_row = vix_df.loc[ts]
    hy_row = hy_oas_df.loc[ts]

    return {
        "spy": {
            "open": float(spy_row.get("open", spy_row["close"])),
            "high": float(spy_row.get("high", spy_row["close"])),
            "low": float(spy_row.get("low", spy_row["close"])),
            "close": float(spy_row["close"]),
            "volume": float(spy_row.get("volume", 0.0)),
        },
        "vix": {
            "open": float(vix_row.get("open", vix_row["close"])),
            "high": float(vix_row.get("high", vix_row["close"])),
            "low": float(vix_row.get("low", vix_row["close"])),
            "close": float(vix_row["close"]),
            "volume": float(vix_row.get("volume", 0.0)),
        },
        "credit": {
            "open": float(hy_row.get("open", hy_row["close"])),
            "high": float(hy_row.get("high", hy_row["close"])),
            "low": float(hy_row.get("low", hy_row["close"])),
            "close": float(hy_row["close"]),
            "volume": float(hy_row.get("volume", 0.0)),
        },
    }


def _build_members_bar(
    sector_member_dfs: Dict[str, pd.DataFrame],
    ts: pd.Timestamp,
) -> Dict[str, Dict[str, float | None]]:
    members_bar: Dict[str, Dict[str, float | None]] = {}

    for ticker, mdf in (sector_member_dfs or {}).items():
        if mdf is None or mdf.empty or ts not in mdf.index or "close" not in mdf.columns:
            continue

        row = mdf.loc[ts]
        members_bar[ticker] = {
            "close": float(row["close"]),
            "prev_close": _get_prev_close(mdf, ts),
        }

    return members_bar


def _to_float_or_str(v: Any) -> Any:
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return str(v) if v is not None else None


def _numeric_equal(a: Any, b: Any, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        af = float(a)
        bf = float(b)
        return abs(af - bf) <= tol
    except Exception:
        return str(a) == str(b)


def _series_value(series: pd.Series, key: str) -> Any:
    return series[key] if key in series.index else None


def run_validation(
    *,
    symbol: str,
    sector: str,
    sector_etf: str | None,
    start_date: str,
    end_date: str,
    base_path: str | Path = DEFAULT_BASE_PATH,
    config_dir: str | Path = DEFAULT_CONFIG_DIR,
    warmup_bars: int = 60,
    symbol_freq: str = "1d",
    sector_freq: str = "1d",
    macro_freq: str = "1d",
    detail_out: str | Path = DEFAULT_OUTPUT_DETAIL,
    summary_out: str | Path = DEFAULT_OUTPUT_SUMMARY,
    tol: float = 1e-9,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info("========== Start column-level validation ==========")

    config_bundle = _load_config_bundle(config_dir)

    symbol_df = _ensure_datetime_index(
        load_symbol_bars(
            base_path=base_path,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            target_freq=_parse_bar_frequency(symbol_freq),
            strict=False,
        )
    )

    sector_member_dfs = load_sector_bars(
        base_path=base_path,
        sector_name=sector,
        start_date=start_date,
        end_date=end_date,
        target_freq=_parse_bar_frequency(sector_freq),
        strict=False,
    )
    sector_member_dfs = {
        k: _ensure_datetime_index(v) for k, v in (sector_member_dfs or {}).items()
    }

    sector_etf_df = _ensure_datetime_index(_resolve_sector_etf_df(sector_member_dfs, sector_etf))

    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_date,
        end_date=end_date,
        target_freq=_parse_bar_frequency(macro_freq),
        strict=False,
    )
    macro_data = {k: _ensure_datetime_index(v) for k, v in macro_data.items()}

    spy_df, vix_df, hy_oas_df = _resolve_macro_inputs(macro_data)
    spy_df = _ensure_datetime_index(spy_df)
    vix_df = _ensure_datetime_index(vix_df)
    hy_oas_df = _ensure_datetime_index(hy_oas_df)

    _log_df("symbol_df", symbol_df)
    _log_df("sector_etf_df", sector_etf_df)
    _log_df("spy_df", spy_df)
    _log_df("vix_df", vix_df)
    _log_df("hy_oas_df", hy_oas_df)

    batch_df = _ensure_datetime_index(
        build_feature_frame(
            symbol_df=symbol_df,
            sector_etf_df=sector_etf_df,
            sector_member_dfs=sector_member_dfs,
            spy_df=spy_df,
            vix_df=vix_df,
            hy_oas_df=hy_oas_df,
            config_bundle=config_bundle,
        )
    )

    if batch_df.empty:
        raise ValueError("Batch feature frame is empty.")

    common_index = batch_df.index.intersection(symbol_df.index)
    common_index = common_index.intersection(sector_etf_df.index)
    common_index = common_index.intersection(spy_df.index)
    common_index = common_index.intersection(vix_df.index)
    common_index = common_index.intersection(hy_oas_df.index)

    if len(common_index) <= warmup_bars:
        raise ValueError(
            f"Not enough aligned rows for validation. rows={len(common_index)}, warmup_bars={warmup_bars}"
        )

    batch_df = batch_df.loc[common_index].copy()
    symbol_df = symbol_df.loc[common_index].copy()
    sector_etf_df = sector_etf_df.loc[common_index].copy()
    spy_df = spy_df.loc[common_index].copy()
    vix_df = vix_df.loc[common_index].copy()
    hy_oas_df = hy_oas_df.loc[common_index].copy()
    for k, df in sector_member_dfs.items():
        sector_member_dfs[k] = df.reindex(common_index)

    members_df = _safe_member_close_frame(sector_member_dfs, common_index)

    warmup_index = common_index[:warmup_bars]
    validate_index = common_index[warmup_bars:]

    logger.info(
        "Validation split | warmup_bars=%s validate_rows=%s first_validate_ts=%s last_validate_ts=%s",
        warmup_bars,
        len(validate_index),
        validate_index.min(),
        validate_index.max(),
    )

    macro_engine = MacroEngine(config_bundle["macro"])
    sector_engine = SectorEngine(config_bundle["sector"])
    symbol_engine = SymbolEngine(config_bundle["symbol"])

    macro_engine.warmup(
        spy_df=spy_df.loc[warmup_index],
        vix_df=vix_df.loc[warmup_index],
        credit_df=hy_oas_df.loc[warmup_index],
    )
    sector_engine.warmup(
        sector_df=sector_etf_df.loc[warmup_index],
        spy_df=spy_df.loc[warmup_index],
        members_df=members_df.loc[warmup_index],
    )
    symbol_engine.warmup(
        symbol_df=symbol_df.loc[warmup_index],
    )

    # Updated mappings based on actual batch column names
    macro_mapping = [
        ("spy_return_z", "spy_trend_z_macro"),
        ("vix_z", "vix_z_macro"),
        ("credit_z", "hy_oas_z_macro"),
        ("trend_factor", "macro_trend_factor_macro"),
        ("vol_factor", "macro_volatility_factor_macro"),
        ("credit_factor", "macro_credit_risk_factor_macro"),
        ("risk_context", "macro_risk_pressure_macro"),
        ("macro_state", "macro_state_macro"),
    ]

    sector_mapping = [
        ("rs_z", "rs_z_sector"),
        ("rs_momentum", "rs_momentum_z_sector"),
        ("breadth", "breadth_frac_sector"),
        ("breadth_momentum", "breadth_momentum_sector"),
        ("vol_z", "vol_ratio_z_sector"),
        ("vol_trend", "vol_trend_z_sector"),
        ("rs_factor", "sector_relative_strength_factor_sector"),
        ("breadth_factor", "sector_breadth_factor_sector"),
        # closest semantic matches from current incremental output
        ("context", "sector_support_score_sector"),
        ("state", "sector_state_sector"),
    ]

    symbol_mapping = [
        ("state", "symbol_state"),
        ("range_position", "symbol_range_position"),
    ]

    details = []

    for ts in validate_index:
        macro_bar = _build_macro_bar(spy_df, vix_df, hy_oas_df, ts)
        sector_bar = _build_sector_bar(sector_etf_df, ts)
        spy_bar = {"close": float(spy_df.loc[ts]["close"])}
        members_bar = _build_members_bar(sector_member_dfs, ts)
        symbol_bar = _build_symbol_bar(symbol_df, ts)

        macro_snapshot = macro_engine.update(macro_bar)
        sector_snapshot = sector_engine.update(sector_bar, spy_bar, members_bar)
        symbol_snapshot = symbol_engine.update(symbol_bar)

        batch_row = batch_df.loc[ts]

        for inc_key, batch_key in macro_mapping:
            inc_val = getattr(macro_snapshot, inc_key)
            batch_val = _series_value(batch_row, batch_key)
            match = _numeric_equal(_to_float_or_str(inc_val), _to_float_or_str(batch_val), tol)
            details.append({
                "datetime": ts,
                "layer": "macro",
                "metric": inc_key,
                "batch_col": batch_key,
                "inc_value": _to_float_or_str(inc_val),
                "batch_value": _to_float_or_str(batch_val),
                "match": match,
            })

        for inc_key, batch_key in sector_mapping:
            inc_val = getattr(sector_snapshot, inc_key)
            batch_val = _series_value(batch_row, batch_key)
            match = _numeric_equal(_to_float_or_str(inc_val), _to_float_or_str(batch_val), tol)
            details.append({
                "datetime": ts,
                "layer": "sector",
                "metric": inc_key,
                "batch_col": batch_key,
                "inc_value": _to_float_or_str(inc_val),
                "batch_value": _to_float_or_str(batch_val),
                "match": match,
            })

        for inc_key, batch_key in symbol_mapping:
            if inc_key == "state":
                inc_val = symbol_snapshot.state
            else:
                inc_val = symbol_snapshot.contexts.get(inc_key, symbol_snapshot.indicators.get(inc_key))

            batch_val = _series_value(batch_row, batch_key)
            match = _numeric_equal(_to_float_or_str(inc_val), _to_float_or_str(batch_val), tol)

            details.append({
                "datetime": ts,
                "layer": "symbol",
                "metric": inc_key,
                "batch_col": batch_key,
                "inc_value": _to_float_or_str(inc_val),
                "batch_value": _to_float_or_str(batch_val),
                "match": match,
            })

    detail_df = pd.DataFrame(details)
    summary_df = (
        detail_df.groupby(["layer", "metric", "batch_col"], dropna=False)["match"]
        .agg(["count", "mean"])
        .reset_index()
        .rename(columns={"mean": "match_rate"})
        .sort_values(["layer", "match_rate", "metric"], ascending=[True, True, True])
    )

    logger.info("========== Column Validation Summary ==========")
    for _, row in summary_df.iterrows():
        logger.info(
            "[%s] %-20s -> %-32s match_rate=%.4f (%s rows)",
            row["layer"],
            row["metric"],
            row["batch_col"],
            row["match_rate"],
            int(row["count"]),
        )

    detail_out = Path(detail_out)
    summary_out = Path(summary_out)
    detail_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.parent.mkdir(parents=True, exist_ok=True)

    detail_df.to_csv(detail_out, index=False)
    summary_df.to_csv(summary_out, index=False)

    logger.info("Detail output saved to %s", detail_out)
    logger.info("Summary output saved to %s", summary_out)

    return detail_df, summary_df


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate batch vs incremental columns")

    parser.add_argument("--symbol", required=True, help="Target symbol, e.g. UUUU")
    parser.add_argument("--sector", required=True, help="Sector name, e.g. rare_earth")
    parser.add_argument("--sector-etf", required=False, help="Explicit sector ETF proxy, e.g. REMX")

    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")

    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)

    parser.add_argument("--symbol-freq", default="1d", choices=["1min", "5min", "15min", "30min", "1h", "1d"])
    parser.add_argument("--sector-freq", default="1d", choices=["1min", "5min", "15min", "30min", "1h", "1d"])
    parser.add_argument("--macro-freq", default="1d", choices=["1min", "5min", "15min", "30min", "1h", "1d"])

    parser.add_argument("--warmup-bars", type=int, default=60)
    parser.add_argument("--tol", type=float, default=1e-9)
    parser.add_argument("--detail-out", default=DEFAULT_OUTPUT_DETAIL)
    parser.add_argument("--summary-out", default=DEFAULT_OUTPUT_SUMMARY)

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    run_validation(
        symbol=args.symbol,
        sector=args.sector,
        sector_etf=args.sector_etf,
        start_date=args.start_date,
        end_date=args.end_date,
        base_path=args.base_path,
        config_dir=args.config_dir,
        warmup_bars=args.warmup_bars,
        symbol_freq=args.symbol_freq,
        sector_freq=args.sector_freq,
        macro_freq=args.macro_freq,
        detail_out=args.detail_out,
        summary_out=args.summary_out,
        tol=args.tol,
    )


if __name__ == "__main__":
    main()
