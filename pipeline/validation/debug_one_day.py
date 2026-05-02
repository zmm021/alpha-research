from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, Any

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


logger = logging.getLogger(__name__)

DEFAULT_BASE_PATH = "data/market"
DEFAULT_CONFIG_DIR = "quant/config"


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
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_config_bundle(config_dir: str | Path) -> dict:
    config_dir = Path(config_dir)
    return {
        "macro": _load_yaml(config_dir / "macro.yaml"),
        "sector": _load_yaml(config_dir / "sector.yaml"),
        "symbol": _load_yaml(config_dir / "symbol.yaml"),
    }


def _resolve_macro_inputs(macro_data: dict[str, pd.DataFrame]):
    if "SPY" not in macro_data or "VIX" not in macro_data:
        raise ValueError("Missing SPY or VIX in macro data")

    spy_df = macro_data["SPY"]
    vix_df = macro_data["VIX"]

    if "HY_OAS" in macro_data:
        hy_oas_df = macro_data["HY_OAS"]
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
            raise ValueError(f"Requested sector ETF proxy {sector_etf} not found")
        return sector_member_dfs[sector_etf]

    for etf_symbol in ["URNM", "URA", "REMX", "XLE", "SMH"]:
        if etf_symbol in sector_member_dfs:
            return sector_member_dfs[etf_symbol]

    raise ValueError("No sector ETF proxy found")


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=True)
    return out.sort_index()


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


def _get_prev_close(df: pd.DataFrame, ts: pd.Timestamp):
    if ts not in df.index:
        return None
    loc = df.index.get_loc(ts)
    if isinstance(loc, slice) or loc <= 0:
        return None
    return float(df.iloc[loc - 1]["close"])


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


def _build_macro_bar(spy_df, vix_df, hy_oas_df, ts):
    spy_row = spy_df.loc[ts]
    vix_row = vix_df.loc[ts]
    hy_row = hy_oas_df.loc[ts]

    return {
        "spy": {"close": float(spy_row["close"])},
        "vix": {"close": float(vix_row["close"])},
        "credit": {"close": float(hy_row["close"])},
    }


def _build_members_bar(sector_member_dfs: Dict[str, pd.DataFrame], ts: pd.Timestamp):
    members_bar = {}
    for ticker, mdf in (sector_member_dfs or {}).items():
        if mdf is None or mdf.empty or ts not in mdf.index or "close" not in mdf.columns:
            continue
        row = mdf.loc[ts]
        members_bar[ticker] = {
            "close": float(row["close"]),
            "prev_close": _get_prev_close(mdf, ts),
        }
    return members_bar


def _print_compare(title: str, pairs: list[tuple[str, Any, Any]]):
    print(f"\n========== {title} ==========")
    for name, inc_val, batch_val in pairs:
        print(f"{name:28s} inc={str(inc_val):20s} batch={str(batch_val):20s}")


def main():
    setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--sector", required=True)
    parser.add_argument("--sector-etf", required=False, default=None)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--debug-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--warmup-bars", type=int, default=60)
    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    args = parser.parse_args()

    config_bundle = _load_config_bundle(args.config_dir)

    symbol_df = _ensure_datetime_index(
        load_symbol_bars(
            base_path=args.base_path,
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            target_freq=_parse_bar_frequency("1d"),
            strict=False,
        )
    )

    sector_member_dfs = load_sector_bars(
        base_path=args.base_path,
        sector_name=args.sector,
        start_date=args.start_date,
        end_date=args.end_date,
        target_freq=_parse_bar_frequency("1d"),
        strict=False,
    )
    sector_member_dfs = {k: _ensure_datetime_index(v) for k, v in (sector_member_dfs or {}).items()}
    sector_etf_df = _ensure_datetime_index(_resolve_sector_etf_df(sector_member_dfs, args.sector_etf))

    macro_data = load_macro_bars(
        base_path=args.base_path,
        start_date=args.start_date,
        end_date=args.end_date,
        target_freq=_parse_bar_frequency("1d"),
        strict=False,
    )
    macro_data = {k: _ensure_datetime_index(v) for k, v in macro_data.items()}
    spy_df, vix_df, hy_oas_df = _resolve_macro_inputs(macro_data)
    spy_df = _ensure_datetime_index(spy_df)
    vix_df = _ensure_datetime_index(vix_df)
    hy_oas_df = _ensure_datetime_index(hy_oas_df)

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

    print("\n========== BATCH SYMBOL COLUMNS ==========")
    for c in batch_df.columns:
        if "symbol" in c:
            print(c)

    print("\n========== BATCH SECTOR COLUMNS ==========")
    for c in batch_df.columns:
        if "sector" in c:
            print(c)

    print("\n========== BATCH MACRO COLUMNS ==========")
    for c in batch_df.columns:
        if "macro" in c or c in ["spy_trend_z_macro", "vix_z_macro", "hy_oas_z_macro"]:
            print(c)

    common_index = batch_df.index.intersection(symbol_df.index)
    common_index = common_index.intersection(sector_etf_df.index)
    common_index = common_index.intersection(spy_df.index)
    common_index = common_index.intersection(vix_df.index)
    common_index = common_index.intersection(hy_oas_df.index)

    batch_df = batch_df.loc[common_index]
    symbol_df = symbol_df.loc[common_index]
    sector_etf_df = sector_etf_df.loc[common_index]
    spy_df = spy_df.loc[common_index]
    vix_df = vix_df.loc[common_index]
    hy_oas_df = hy_oas_df.loc[common_index]
    for k, df in sector_member_dfs.items():
        sector_member_dfs[k] = df.reindex(common_index)

    members_df = _safe_member_close_frame(sector_member_dfs, common_index)

    warmup_index = common_index[:args.warmup_bars]
    validate_index = common_index[args.warmup_bars:]

    debug_ts = pd.Timestamp(args.debug_date, tz="UTC")
    if debug_ts not in validate_index:
        raise ValueError(f"debug date {debug_ts} not in validate range")

    macro_engine = MacroEngine(config_bundle["macro"])
    sector_engine = SectorEngine(config_bundle["sector"])
    symbol_engine = SymbolEngine(config_bundle["symbol"])

    macro_engine.warmup(
        spy_df=spy_df.loc[warmup_index],
        vix_df=vix_df.loc[warmup_index],
        credit_df=hy_oas_df.loc[warmup_index],
    )
    print("\n========== WARMUP END CHECK ==========")
    print(f"warmup last spy close: {macro_engine.prev_spy_close}")
    print(f"warmup prev state: {macro_engine.prev_state}")

    sector_engine.warmup(
        sector_df=sector_etf_df.loc[warmup_index],
        spy_df=spy_df.loc[warmup_index],
        members_df=members_df.loc[warmup_index],
    )
    symbol_engine.warmup(
        symbol_df=symbol_df.loc[warmup_index],
    )

    for ts in validate_index:
        macro_bar = _build_macro_bar(spy_df, vix_df, hy_oas_df, ts)
        sector_bar = _build_sector_bar(sector_etf_df, ts)
        spy_bar = {"close": float(spy_df.loc[ts]["close"])}
        members_bar = _build_members_bar(sector_member_dfs, ts)
        symbol_bar = _build_symbol_bar(symbol_df, ts)

        macro_snapshot = macro_engine.update(macro_bar)
        sector_snapshot = sector_engine.update(sector_bar, spy_bar, members_bar)
        symbol_snapshot = symbol_engine.update(symbol_bar)

        if ts == debug_ts:
            batch_row = batch_df.loc[ts]

            print("\n========== RAW MACRO INPUT BAR ==========")
            print(macro_bar)

            print("\n========== RAW BATCH MACRO ROW ==========")
            for c in [
                "spy_trend_z_macro",
                "vix_z_macro",
                "hy_oas_z_macro",
                "macro_trend_factor_macro",
                "macro_volatility_factor_macro",
                "macro_credit_risk_factor_macro",
                "macro_trend_strength_macro",
                "macro_risk_pressure_macro",
                "macro_state_macro",
            ]:
                print(f"{c:35s} {batch_row.get(c)}")

            print("\n========== RAW INCREMENTAL MACRO SNAPSHOT ==========")
            print(f"{'spy_return_z':35s} {macro_snapshot.spy_return_z}")
            print(f"{'vix_z':35s} {macro_snapshot.vix_z}")
            print(f"{'credit_z':35s} {macro_snapshot.credit_z}")
            print(f"{'trend_factor':35s} {macro_snapshot.trend_factor}")
            print(f"{'vol_factor':35s} {macro_snapshot.vol_factor}")
            print(f"{'credit_factor':35s} {macro_snapshot.credit_factor}")
            print(f"{'risk_context':35s} {macro_snapshot.risk_context}")
            print(f"{'macro_state':35s} {macro_snapshot.macro_state}")

            _print_compare(
                f"MACRO {ts.date()}",
                [
                    ("spy_return_z", macro_snapshot.spy_return_z, batch_row.get("spy_trend_z_macro")),
                    ("vix_z", macro_snapshot.vix_z, batch_row.get("vix_z_macro")),
                    ("credit_z", macro_snapshot.credit_z, batch_row.get("hy_oas_z_macro")),
                    ("trend_factor", macro_snapshot.trend_factor, batch_row.get("macro_trend_factor_macro")),
                    ("vol_factor", macro_snapshot.vol_factor, batch_row.get("macro_volatility_factor_macro")),
                    ("credit_factor", macro_snapshot.credit_factor, batch_row.get("macro_credit_risk_factor_macro")),
                    ("risk_context", macro_snapshot.risk_context, batch_row.get("macro_risk_pressure_macro")),
                    ("macro_state", macro_snapshot.macro_state, batch_row.get("macro_state_macro")),
                ],
            )

            print("\n========== RAW BATCH SECTOR ROW ==========")
            for c in [
                "rs_z_sector",
                "rs_momentum_z_sector",
                "breadth_frac_sector",
                "breadth_momentum_sector",
                "vol_ratio_z_sector",
                "vol_trend_z_sector",
                "sector_relative_strength_factor_sector",
                "sector_breadth_factor_sector",
                "sector_participation_factor_sector",
                "sector_momentum_factor_sector",
                "sector_support_score_sector",
                "sector_breadth_health_sector",
                "sector_momentum_sector",
                "sector_state_sector",
            ]:
                print(f"{c:35s} {batch_row.get(c)}")

            print("\n========== RAW INCREMENTAL SECTOR SNAPSHOT ==========")
            print(f"{'rs_z':35s} {sector_snapshot.rs_z}")
            print(f"{'rs_momentum':35s} {sector_snapshot.rs_momentum}")
            print(f"{'breadth':35s} {sector_snapshot.breadth}")
            print(f"{'breadth_ma':35s} {sector_snapshot.breadth_ma}")
            print(f"{'breadth_momentum':35s} {sector_snapshot.breadth_momentum}")
            print(f"{'vol_z':35s} {sector_snapshot.vol_z}")
            print(f"{'vol_trend':35s} {sector_snapshot.vol_trend}")
            print(f"{'rs_factor':35s} {sector_snapshot.rs_factor}")
            print(f"{'breadth_factor':35s} {sector_snapshot.breadth_factor}")
            print(f"{'vol_factor':35s} {sector_snapshot.vol_factor}")
            print(f"{'context':35s} {sector_snapshot.context}")
            print(f"{'state':35s} {sector_snapshot.state}")

            _print_compare(
                f"SECTOR {ts.date()}",
                [
                    ("rs_z", sector_snapshot.rs_z, batch_row.get("rs_z_sector")),
                    ("rs_momentum", sector_snapshot.rs_momentum, batch_row.get("rs_momentum_z_sector")),
                    ("breadth", sector_snapshot.breadth, batch_row.get("breadth_frac_sector")),
                    ("breadth_momentum", sector_snapshot.breadth_momentum, batch_row.get("breadth_momentum_sector")),
                    ("vol_z", sector_snapshot.vol_z, batch_row.get("vol_ratio_z_sector")),
                    ("vol_trend", sector_snapshot.vol_trend, batch_row.get("vol_trend_z_sector")),
                    ("rs_factor", sector_snapshot.rs_factor, batch_row.get("sector_relative_strength_factor_sector")),
                    ("breadth_factor", sector_snapshot.breadth_factor, batch_row.get("sector_breadth_factor_sector")),
                    ("context", sector_snapshot.context, batch_row.get("sector_support_score_sector")),
                    ("state", sector_snapshot.state, batch_row.get("sector_state_sector")),
                ],
            )

            print("\n========== RAW BATCH SYMBOL ROW ==========")
            for c in [
                "symbol_trend_factor",
                "symbol_trend_slope_factor",
                "symbol_trend_slope_raw",
                "symbol_long_slope_raw",
                "symbol_volatility_factor",
                "symbol_liquidity_factor",
                "symbol_position_factor",
                "symbol_range_position_factor",
                "symbol_intraday_intent_factor",
                "symbol_trend_strength",
                "symbol_trend_slope",
                "symbol_volatility_state",
                "symbol_position_quality",
                "symbol_range_position",
                "symbol_intraday_intent",
                "symbol_liquidity_quality",
                "symbol_exhaustion_risk",
                "symbol_failure_risk",
                "symbol_reversal_pressure",
                "symbol_state",
            ]:
                print(f"{c:35s} {batch_row.get(c)}")

            print("\n========== RAW INCREMENTAL SYMBOL SNAPSHOT ==========")
            print(f"{'range_position':35s} {symbol_snapshot.indicators.get('range_position')}")
            print(f"{'state':35s} {symbol_snapshot.state}")
            print(f"{'factors':35s} {symbol_snapshot.factors}")
            print(f"{'contexts':35s} {symbol_snapshot.contexts}")

            _print_compare(
                f"SYMBOL {ts.date()}",
                [
                    ("range_position", symbol_snapshot.indicators.get("range_position"), batch_row.get("symbol_range_position")),
                    ("state", symbol_snapshot.state, batch_row.get("symbol_state")),
                ],
            )
            break


if __name__ == "__main__":
    main()