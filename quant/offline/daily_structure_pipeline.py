from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from utils.bar_utls import BarFrequency
from utils.parquet_loader import (
    load_macro_bars,
    load_sector_bars,
    load_symbol_bars,
)

from quant.macro.indicators import compute_macro_indicators
from quant.macro.factors import compute_macro_factors, compute_macro_structure
from quant.macro.state import compute_macro_states

from quant.sector.indicators import compute_sector_indicators
from quant.sector.factors import compute_sector_factors, compute_sector_structure
from quant.sector.state import compute_sector_states

from quant.symbol.indicators import compute_symbol_indicators
from quant.symbol.factors import compute_symbol_factors, compute_symbol_structure
from quant.symbol.state import compute_symbol_states

from postgres.meta_repo import get_sector_symbols
from postgres.daily_structure_repo import (
    create_daily_structure_run,
    finish_daily_structure_run_with_end_date,
    fail_daily_structure_run,
    get_last_successful_daily_structure_run,
    upsert_daily_macro_structure,
    upsert_daily_sector_structure,
    upsert_daily_symbol_structure,
)


logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "quant/offline/daily_structure_config.yaml"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def _load_yaml(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_config_bundle(config_dir: str | Path) -> dict:
    config_dir = Path(config_dir)
    return {
        "macro": _load_yaml(config_dir / "macro.yaml"),
        "sector": _load_yaml(config_dir / "sector.yaml"),
        "symbol": _load_yaml(config_dir / "symbol.yaml"),
    }


def _to_date(d: str | date) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d), "%Y-%m-%d").date()


def _date_str(d: str | date) -> str:
    return _to_date(d).isoformat()


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _run_id(start_date: date, end_date: date) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"daily_structure_{start_date.isoformat()}_{end_date.isoformat()}_{ts}"


def _get_run_window(cfg: dict) -> tuple[date, date]:
    default_start = _to_date(cfg["default_start_date"])
    yesterday = _yesterday()

    last_run = get_last_successful_daily_structure_run()

    if not last_run:
        return default_start, yesterday

    last_end = _to_date(last_run["end_date"])
    next_start = last_end + timedelta(days=1)

    return next_start, yesterday


def _with_lookback(start_date: date, lookback_days: int) -> date:
    return start_date - timedelta(days=lookback_days)


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=True)
    return out.sort_index()


def _index_date(ts) -> date:
    return pd.Timestamp(ts).date()


def _enum_value(v: Any) -> Any:
    if hasattr(v, "value"):
        return v.value
    return v


def _clean_value(v: Any) -> Any:
    v = _enum_value(v)
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    return v


def _resolve_macro_inputs(
    macro_data: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "SPY" not in macro_data or "VIX" not in macro_data:
        raise ValueError("Missing required macro inputs: SPY / VIX")

    spy_df = macro_data["SPY"]
    vix_df = macro_data["VIX"]

    if "HY_OAS" in macro_data:
        credit_df = macro_data["HY_OAS"]
    elif "TLT" in macro_data:
        logger.warning("HY_OAS not found, fallback to TLT")
        credit_df = macro_data["TLT"]
    else:
        raise ValueError("Missing HY_OAS and fallback TLT")

    return spy_df, vix_df, credit_df


def _resolve_sector_etf_df(
    sector_member_dfs: dict[str, pd.DataFrame],
    sector_etf: str,
) -> pd.DataFrame | None:
    if sector_etf not in sector_member_dfs:
        logger.warning("Sector ETF %s not found in sector bars, skip sector", sector_etf)
        return None
    return sector_member_dfs[sector_etf]


def _safe_member_dfs(
    *,
    base_path: str,
    sector_name: str,
    member_symbols: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    dfs: dict[str, pd.DataFrame] = {}

    for symbol in member_symbols:
        try:
            df = load_symbol_bars(
                base_path=base_path,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                target_freq=BarFrequency.DAY_1,
                strict=False,
            )
            if df is not None and not df.empty:
                dfs[symbol] = _ensure_datetime_index(df)
        except Exception as e:
            logger.warning("Skip sector member %s/%s: %s", sector_name, symbol, e)

    return dfs


def _compute_macro_daily(
    *,
    base_path: str,
    start_load: date,
    end_date: date,
    run_start: date,
    config: dict,
    run_id: str,
) -> date | None:
    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_load.isoformat(),
        end_date=end_date.isoformat(),
        target_freq=BarFrequency.DAY_1,
        strict=False,
    )
    macro_data = {k: _ensure_datetime_index(v) for k, v in macro_data.items()}

    spy_df, vix_df, credit_df = _resolve_macro_inputs(macro_data)

    ind = compute_macro_indicators(
        spy_df=spy_df,
        vix_df=vix_df,
        hy_oas_df=credit_df,
        config=config,
    )
    fac = compute_macro_factors(ind, config)
    struct = compute_macro_structure(fac, config)
    states = compute_macro_states(struct, config)

    full = ind.join(fac).join(struct)
    full["macro_state"] = states

    actual_last: date | None = None

    for ts, row in full.iterrows():
        as_of_date = _index_date(ts)
        if as_of_date < run_start or as_of_date > end_date:
            continue

        record = {
            "as_of_date": as_of_date,
            "macro_state": _clean_value(row.get("macro_state")),
            "run_id": run_id,
        }

        for col, value in row.items():
            if col == "macro_state":
                continue
            record[col] = _clean_value(value)

        upsert_daily_macro_structure(record)
        actual_last = as_of_date

    return actual_last


def _compute_sector_daily(
    *,
    base_path: str,
    sector_name: str,
    sector_etf: str,
    member_asset_type: str | None,
    start_load: date,
    end_date: date,
    run_start: date,
    config: dict,
    run_id: str,
) -> date | None:
    member_symbols = get_sector_symbols(
        sector_name=sector_name,
        asset_type=member_asset_type,
    )

    if sector_etf not in member_symbols:
        member_symbols.append(sector_etf)

    sector_member_dfs = _safe_member_dfs(
        base_path=base_path,
        sector_name=sector_name,
        member_symbols=member_symbols,
        start_date=start_load.isoformat(),
        end_date=end_date.isoformat(),
    )

    if not sector_member_dfs:
        logger.warning("No sector data for %s, skip", sector_name)
        return None

    sector_etf_df = _resolve_sector_etf_df(sector_member_dfs, sector_etf)
    if sector_etf_df is None or sector_etf_df.empty:
        return None

    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_load.isoformat(),
        end_date=end_date.isoformat(),
        target_freq=BarFrequency.DAY_1,
        strict=False,
    )
    macro_data = {k: _ensure_datetime_index(v) for k, v in macro_data.items()}
    spy_df = macro_data.get("SPY")
    if spy_df is None or spy_df.empty:
        raise ValueError("Missing SPY for sector computation")

    ind = compute_sector_indicators(
        sector_etf_df=sector_etf_df,
        member_dfs=sector_member_dfs,
        spy_df=spy_df,
        config=config,
    )
    fac = compute_sector_factors(ind, config)
    struct = compute_sector_structure(fac, config)
    states = compute_sector_states(struct, config)

    full = ind.join(fac).join(struct)
    full["sector_state"] = states

    actual_last: date | None = None

    for ts, row in full.iterrows():
        as_of_date = _index_date(ts)
        if as_of_date < run_start or as_of_date > end_date:
            continue

        record = {
            "as_of_date": as_of_date,
            "sector_name": sector_name,
            "sector_etf": sector_etf,
            "sector_state": _clean_value(row.get("sector_state")),
            "run_id": run_id,
        }

        for col, value in row.items():
            if col == "sector_state":
                continue
            record[col] = _clean_value(value)

        upsert_daily_sector_structure(record)
        actual_last = as_of_date

    return actual_last


def _compute_symbol_daily(
    *,
    base_path: str,
    symbol: str,
    start_load: date,
    end_date: date,
    run_start: date,
    config: dict,
    run_id: str,
) -> date | None:
    df = load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        start_date=start_load.isoformat(),
        end_date=end_date.isoformat(),
        target_freq=BarFrequency.DAY_1,
        strict=False,
    )
    df = _ensure_datetime_index(df)

    if df is None or df.empty:
        logger.warning("No daily symbol data for %s, skip", symbol)
        return None

    ind = compute_symbol_indicators(df, config)
    fac = compute_symbol_factors(ind, config)
    struct = compute_symbol_structure(fac, config)
    states = compute_symbol_states(struct, config)

    full = ind.join(fac).join(struct)
    full["symbol_state"] = states

    actual_last: date | None = None

    for ts, row in full.iterrows():
        as_of_date = _index_date(ts)
        if as_of_date < run_start or as_of_date > end_date:
            continue

        record = {
            "as_of_date": as_of_date,
            "symbol": symbol,
            "symbol_state": _clean_value(row.get("symbol_state")),
            "run_id": run_id,
        }

        allowed_cols = {
            "ma20",
            "ma50",
            "ma20_slope",
            "ma50_slope",
            "atr_pct",
            "volume_ratio",
            "range_position_short",
            "range_position_mid",
            "distance_to_high_short",
            "distance_to_high_mid",

            "symbol_trend_factor",
            "symbol_trend_slope_factor",
            "symbol_volatility_factor",
            "symbol_liquidity_factor",
            "symbol_position_factor_short",
            "symbol_position_factor_mid",
            "symbol_range_position_factor_short",
            "symbol_range_position_factor_mid",

            "symbol_trend_strength",
            "symbol_trend_slope",
            "symbol_volatility_state",
            "symbol_liquidity_quality",
            "symbol_position_quality_short",
            "symbol_position_quality_mid",
            "symbol_range_position_short",
            "symbol_range_position_mid",
            "symbol_reversal_pressure",
            "symbol_exhaustion_risk",
            "symbol_failure_risk",
        }

        for col, value in row.items():
            if col in allowed_cols:
                record[col] = _clean_value(value)

        upsert_daily_symbol_structure(record)
        actual_last = as_of_date

    return actual_last


def run_daily_structure_pipeline(config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
    cfg_root = _load_yaml(config_path)
    cfg = cfg_root["daily_structure"]

    config_bundle = _load_config_bundle(cfg["config_dir"])

    run_start, run_end = _get_run_window(cfg)
    logger.info("Loaded daily_structure cfg: %s", cfg)
    logger.info("Resolved run_start=%s run_end=%s", run_start, run_end)
    logger.info("Today=%s yesterday=%s", date.today(), _yesterday())
    logger.info("Last successful run: %s", get_last_successful_daily_structure_run())
    if run_start > run_end:
        logger.info("No new dates to process. start=%s end=%s", run_start, run_end)
        return

    lookback_days = int(cfg.get("lookback_days", 1200))
    start_load = _with_lookback(run_start, lookback_days)

    run_id = _run_id(run_start, run_end)

    symbols = cfg.get("symbols", []) or []
    sectors = [s["sector_name"] for s in cfg.get("sectors", []) or []]

    logger.info("Start daily structure run: %s", run_id)
    logger.info("Run window: %s -> %s, load from %s", run_start, run_end, start_load)

    create_daily_structure_run(
        run_id=run_id,
        start_date=run_start,
        end_date=run_end,
        symbols=symbols,
        sectors=sectors,
    )

    actual_ends: list[date] = []

    try:
        if cfg.get("macro", {}).get("enabled", True):
            actual = _compute_macro_daily(
                base_path=cfg["base_path"],
                start_load=start_load,
                end_date=run_end,
                run_start=run_start,
                config=config_bundle["macro"],
                run_id=run_id,
            )
            if actual:
                actual_ends.append(actual)

        for sector_cfg in cfg.get("sectors", []) or []:
            actual = _compute_sector_daily(
                base_path=cfg["base_path"],
                sector_name=sector_cfg["sector_name"],
                sector_etf=sector_cfg["sector_etf"],
                member_asset_type=sector_cfg.get("member_asset_type"),
                start_load=start_load,
                end_date=run_end,
                run_start=run_start,
                config=config_bundle["sector"],
                run_id=run_id,
            )
            if actual:
                actual_ends.append(actual)

        for symbol in symbols:
            actual = _compute_symbol_daily(
                base_path=cfg["base_path"],
                symbol=symbol,
                start_load=start_load,
                end_date=run_end,
                run_start=run_start,
                config=config_bundle["symbol"],
                run_id=run_id,
            )
            if actual:
                actual_ends.append(actual)

        if not actual_ends:
            logger.warning("No rows written. Mark run failed.")
            fail_daily_structure_run(run_id, "No rows written")
            return

        actual_end = min(max(actual_ends), run_end)

        finish_daily_structure_run_with_end_date(
            run_id=run_id,
            actual_end_date=actual_end,
        )

        logger.info("Daily structure run succeeded. actual_end=%s", actual_end)

    except Exception as e:
        logger.exception("Daily structure run failed")
        fail_daily_structure_run(run_id, str(e))
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run daily offline structure pipeline")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to daily structure config yaml",
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    run_daily_structure_pipeline(args.config)


if __name__ == "__main__":
    main()