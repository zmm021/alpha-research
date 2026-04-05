from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from ib_insync import IB, Stock, util

from config import FILE_FORMAT, IB_CLIENT_ID, IB_HOST, IB_PORT, get_historical_dir

DEFAULT_BAR_SIZE = "1 min"
DEFAULT_WHAT_TO_SHOW = "TRADES"
DEFAULT_PACING_SLEEP_SECONDS = 0.5

YEAR_PATTERN = re.compile(r"^\d{4}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def connect_ib(host: str = IB_HOST, port: int = IB_PORT, client_id: int = IB_CLIENT_ID) -> IB:
    ib = IB()
    ib.connect(host, port, clientId=client_id)
    if not ib.isConnected():
        raise RuntimeError(f"Failed to connect to IBKR at {host}:{port}, clientId={client_id}")
    return ib


def get_stock_contract(symbol: str) -> Stock:
    return Stock(symbol.upper(), "SMART", "USD")


def _file_ext(file_format: str) -> str:
    if file_format not in {"parquet", "csv"}:
        raise ValueError(f"Unsupported file format: {file_format}")
    return "parquet" if file_format == "parquet" else "csv"


def _historical_root(symbol: str) -> Path:
    root = get_historical_dir(symbol.upper())
    root.mkdir(parents=True, exist_ok=True)
    return root


def _year_dir(symbol: str, year: int) -> Path:
    return _historical_root(symbol) / f"{year:04d}"


def _month_dir(symbol: str, year: int, month: int) -> Path:
    return _year_dir(symbol, year) / f"{year:04d}-{month:02d}"


def _day_path(symbol: str, target_date: date, file_format: str = FILE_FORMAT) -> Path:
    ext = _file_ext(file_format)
    return _month_dir(symbol, target_date.year, target_date.month) / f"{target_date.isoformat()}.{ext}"


def _meta_path(symbol: str) -> Path:
    return _historical_root(symbol) / "_meta.json"


def _remove_path_if_exists(path: Path) -> None:
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _save_df(df: pd.DataFrame, path: Path, file_format: str = FILE_FORMAT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        print(f"[WARN] Empty dataframe, skip saving: {path}")
        return

    if file_format == "parquet":
        df.to_parquet(path, index=False)
    elif file_format == "csv":
        df.to_csv(path, index=False)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

    print(f"[OK] Saved: {path}")


def _normalize_bars_to_df(bars) -> pd.DataFrame:
    df = util.df(bars)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _fetch_history(
    ib: IB,
    symbol: str,
    *,
    end_dt: datetime,
    duration_str: str,
    bar_size: str = DEFAULT_BAR_SIZE,
    what_to_show: str = DEFAULT_WHAT_TO_SHOW,
    use_rth: bool = True,
) -> pd.DataFrame:
    contract = get_stock_contract(symbol)
    ib.qualifyContracts(contract)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_dt.strftime("%Y%m%d %H:%M:%S"),
        durationStr=duration_str,
        barSizeSetting=bar_size,
        whatToShow=what_to_show,
        useRTH=use_rth,
        formatDate=1,
    )
    return _normalize_bars_to_df(bars)


def fetch_month_history(
    ib: IB,
    symbol: str,
    *,
    year: int,
    month: int,
    use_rth: bool = True,
) -> pd.DataFrame:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")

    if month == 12:
        end_dt = datetime(year + 1, 1, 1, 0, 0, 0)
    else:
        end_dt = datetime(year, month + 1, 1, 0, 0, 0)

    print(f"[INFO] Fetching month history for {symbol}: {year}-{month:02d}")
    return _fetch_history(
        ib,
        symbol,
        end_dt=end_dt,
        duration_str="1 M",
        use_rth=use_rth,
    )


def fetch_day_history(
    ib: IB,
    symbol: str,
    *,
    target_date: date,
    use_rth: bool = True,
) -> pd.DataFrame:
    end_dt = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    print(f"[INFO] Fetching day history for {symbol}: {target_date.isoformat()}")
    return _fetch_history(
        ib,
        symbol,
        end_dt=end_dt,
        duration_str="1 D",
        use_rth=use_rth,
    )


def fetch_year_history(
    ib: IB,
    symbol: str,
    *,
    year: int,
    use_rth: bool = True,
    pacing_sleep_seconds: float = DEFAULT_PACING_SLEEP_SECONDS,
) -> list[tuple[int, int, pd.DataFrame]]:
    monthly_results: list[tuple[int, int, pd.DataFrame]] = []
    for month in range(1, 13):
        df_month = fetch_month_history(ib, symbol, year=year, month=month, use_rth=use_rth)
        monthly_results.append((year, month, df_month))
        ib.sleep(pacing_sleep_seconds)
    return monthly_results


def _write_month_df_to_daily_files(
    symbol: str,
    df: pd.DataFrame,
    *,
    year: int,
    month: int,
    file_format: str = FILE_FORMAT,
) -> list[Path]:
    written_paths: list[Path] = []
    if df.empty:
        print(f"[WARN] No data returned for {symbol} {year:04d}-{month:02d}")
        return written_paths

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working["trade_date"] = working["date"].dt.strftime("%Y-%m-%d")

    for day_str, df_day in working.groupby("trade_date", sort=True):
        day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        out_path = _day_path(symbol, day_date, file_format=file_format)
        _save_df(df_day.drop(columns=["trade_date"]), out_path, file_format=file_format)
        written_paths.append(out_path)

    return written_paths


def _scan_meta(symbol: str) -> dict:
    root = _historical_root(symbol)
    available_years: list[str] = []
    available_months: list[str] = []

    for year_dir in sorted([p for p in root.iterdir() if p.is_dir() and YEAR_PATTERN.match(p.name)]):
        available_years.append(year_dir.name)
        for month_dir in sorted([p for p in year_dir.iterdir() if p.is_dir() and MONTH_PATTERN.match(p.name)]):
            available_months.append(month_dir.name)

    return {
        "symbol": symbol.upper(),
        "available_years": available_years,
        "available_months": available_months,
        "last_updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def update_meta(symbol: str) -> Path:
    meta = _scan_meta(symbol)
    path = _meta_path(symbol)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Updated meta: {path}")
    return path


def store_month_history(
    ib: IB,
    symbol: str,
    *,
    year: int,
    month: int,
    use_rth: bool = True,
    file_format: str = FILE_FORMAT,
    replace_existing: bool = True,
) -> Path:
    month_dir = _month_dir(symbol, year, month)
    if replace_existing:
        _remove_path_if_exists(month_dir)

    df = fetch_month_history(ib, symbol, year=year, month=month, use_rth=use_rth)
    _write_month_df_to_daily_files(symbol, df, year=year, month=month, file_format=file_format)
    update_meta(symbol)
    return month_dir


def store_day_history(
    ib: IB,
    symbol: str,
    *,
    target_date: date,
    use_rth: bool = True,
    file_format: str = FILE_FORMAT,
    replace_existing: bool = True,
) -> Path:
    day_path = _day_path(symbol, target_date, file_format=file_format)
    if replace_existing:
        _remove_path_if_exists(day_path)

    df = fetch_day_history(ib, symbol, target_date=target_date, use_rth=use_rth)
    _save_df(df, day_path, file_format=file_format)
    update_meta(symbol)
    return day_path


def store_year_history(
    ib: IB,
    symbol: str,
    *,
    year: int,
    use_rth: bool = True,
    file_format: str = FILE_FORMAT,
    replace_existing: bool = True,
) -> Path:
    year_dir = _year_dir(symbol, year)
    if replace_existing:
        _remove_path_if_exists(year_dir)

    monthly_results = fetch_year_history(ib, symbol, year=year, use_rth=use_rth)
    for y, month, df_month in monthly_results:
        _write_month_df_to_daily_files(symbol, df_month, year=y, month=month, file_format=file_format)

    update_meta(symbol)
    return year_dir
