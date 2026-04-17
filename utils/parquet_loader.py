from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import pandas_market_calendars as mcal

from postgres import meta_repo
from utils.bar_schema import prepare_bar_dataframe
from utils.bar_utls import (
    BarFrequency,
    aggregate_ohlcv_bars,
    infer_session_date,
)

ScopeType = Literal["symbol", "sector", "macro"]


# =========================
# Path Helpers
# =========================

def _symbol_base_path(base_path: Path, symbol: str) -> Path:
    return base_path / symbol / "historical"


def _daily_file_path(base_path: Path, symbol: str, date_str: str) -> Path:
    return (
        _symbol_base_path(base_path, symbol)
        / date_str[:4]
        / date_str[:7]
        / f"{date_str}.parquet"
    )


# =========================
# Trading Calendar Helpers
# =========================

def _trading_dates(
    start_date: str,
    end_date: str,
    calendar_name: str = "NYSE",
) -> list[str]:
    """
    Return actual exchange trading dates, not generic business dates.
    This avoids false missing-file errors on market holidays.
    """
    calendar = mcal.get_calendar(calendar_name)
    schedule = calendar.schedule(start_date=start_date, end_date=end_date)
    return schedule.index.strftime("%Y-%m-%d").tolist()


def _month_date_range(month: str) -> tuple[str, str]:
    dt = pd.Timestamp(f"{month}-01")
    start = dt.replace(day=1)
    end = start + pd.offsets.MonthEnd(1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _year_date_range(year: int) -> tuple[str, str]:
    return f"{year}-01-01", f"{year}-12-31"


def _resolve_date_range(
    start_date: str | None,
    end_date: str | None,
    year: int | None,
    month: str | None,
) -> tuple[str, str]:
    provided_modes = sum(
        [
            int(start_date is not None or end_date is not None),
            int(year is not None),
            int(month is not None),
        ]
    )

    if provided_modes != 1:
        raise ValueError(
            "Provide exactly one of: "
            "(start_date and end_date), year, or month"
        )

    if year is not None:
        return _year_date_range(year)

    if month is not None:
        return _month_date_range(month)

    if start_date is None or end_date is None:
        raise ValueError("Both start_date and end_date are required")

    return start_date, end_date


# =========================
# Validation Helpers
# =========================

def _validate_loaded_df(df: pd.DataFrame, symbol: str, date_str: str) -> pd.DataFrame:
    if df.empty:
        raise ValueError(f"Loaded empty parquet for symbol={symbol}, date={date_str}")

    df = prepare_bar_dataframe(df)

    if df.empty:
        raise ValueError(
            f"Prepared dataframe is empty for symbol={symbol}, date={date_str}"
        )

    return df


# =========================
# DatetimeIndex Helper
# =========================

def _set_datetime_index(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if df.empty:
        return df

    if date_col not in df.columns:
        raise ValueError(f"Missing date column: {date_col}")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], utc=True, errors="coerce")

    if out[date_col].isna().any():
        raise ValueError(f"Failed to parse some datetime values in column: {date_col}")

    out = out.sort_values(date_col).set_index(date_col, drop=False)
    out.index.name = date_col
    return out


# =========================
# Load Core
# =========================

def _load_daily_parquet(base_path: Path, symbol: str, date_str: str) -> pd.DataFrame:
    path = _daily_file_path(base_path, symbol, date_str)
    if not path.exists():
        raise FileNotFoundError(f"Missing parquet file: {path}")

    df = pd.read_parquet(path)
    return _validate_loaded_df(df, symbol, date_str)


def _load_symbol_raw_range(
    base_path: Path,
    symbol: str,
    start_date: str,
    end_date: str,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> pd.DataFrame:
    dfs: list[pd.DataFrame] = []
    missing_dates: list[str] = []

    for date_str in _trading_dates(start_date, end_date, calendar_name=calendar_name):
        path = _daily_file_path(base_path, symbol, date_str)

        if not path.exists():
            missing_dates.append(date_str)
            continue

        df = pd.read_parquet(path)
        df = _validate_loaded_df(df, symbol, date_str)
        dfs.append(df)

    if missing_dates and strict:
        raise FileNotFoundError(
            f"Missing parquet files for symbol={symbol}, "
            f"range={start_date}~{end_date}, missing_dates={missing_dates}"
        )

    if not dfs:
        raise ValueError(
            f"No parquet data loaded for symbol={symbol}, "
            f"range={start_date}~{end_date}"
        )

    out = pd.concat(dfs, ignore_index=True)
    out = prepare_bar_dataframe(out)
    out = _set_datetime_index(out, date_col="date")
    return out


# =========================
# Frequency Helpers
# =========================

def _apply_frequency(
    df: pd.DataFrame,
    target_freq: BarFrequency | None,
) -> pd.DataFrame:
    if df.empty or target_freq is None or target_freq == BarFrequency.MIN_1:
        return _set_datetime_index(df, date_col="date")

    if not isinstance(df.index, pd.DatetimeIndex):
        df = _set_datetime_index(df, date_col="date")

    df_for_agg = df.reset_index(drop=True)
    df_for_agg = infer_session_date(df_for_agg, date_col="date", output_col="session_date")

    out = aggregate_ohlcv_bars(
        df=df_for_agg,
        target_freq=target_freq,
        date_col="date",
        session_col="session_date",
        keep_partial_last_bar=True,
    )
    return _set_datetime_index(out, date_col="date")


# =========================
# Public APIs
# =========================

def load_symbol_bars(
    *,
    base_path: str | Path,
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    month: str | None = None,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> pd.DataFrame:
    """
    Load one symbol as a single DataFrame.

    Supported modes (exactly one):
    1. start_date + end_date
    2. year
    3. month (YYYY-MM)
    """
    resolved_start, resolved_end = _resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        year=year,
        month=month,
    )

    raw = _load_symbol_raw_range(
        base_path=Path(base_path),
        symbol=symbol,
        start_date=resolved_start,
        end_date=resolved_end,
        strict=strict,
        calendar_name=calendar_name,
    )

    return _apply_frequency(raw, target_freq)


def load_sector_bars(
    *,
    base_path: str | Path,
    sector_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    month: str | None = None,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    asset_type: str | None = None,
    calendar_name: str = "NYSE",
) -> dict[str, pd.DataFrame]:
    """
    Load all symbols in one sector.
    Returns dict[symbol, pd.DataFrame]
    """
    if asset_type is None:
        symbols = meta_repo.get_sector_symbols(sector_name=sector_name)
    else:
        symbols = meta_repo.get_sector_symbols(
            sector_name=sector_name,
            asset_type=asset_type,
        )

    if not symbols:
        raise ValueError(f"No sector symbols found for sector={sector_name}")

    out: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        df = load_symbol_bars(
            base_path=base_path,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            year=year,
            month=month,
            target_freq=target_freq,
            strict=strict,
            calendar_name=calendar_name,
        )
        out[symbol] = df

    return out


def load_macro_bars(
    *,
    base_path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    month: str | None = None,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> dict[str, pd.DataFrame]:
    """
    Load all macro symbols.
    Returns dict[symbol, pd.DataFrame]
    """
    symbols = meta_repo.get_macro_symbols()

    if not symbols:
        raise ValueError("No macro symbols found")

    out: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        df = load_symbol_bars(
            base_path=base_path,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            year=year,
            month=month,
            target_freq=target_freq,
            strict=strict,
            calendar_name=calendar_name,
        )
        out[symbol] = df

    return out


# =========================
# Optional Convenience Wrappers
# =========================

def load_symbol_bars_by_year(
    *,
    base_path: str | Path,
    symbol: str,
    year: int,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> pd.DataFrame:
    return load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        year=year,
        target_freq=target_freq,
        strict=strict,
        calendar_name=calendar_name,
    )


def load_symbol_bars_by_month(
    *,
    base_path: str | Path,
    symbol: str,
    month: str,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> pd.DataFrame:
    return load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        month=month,
        target_freq=target_freq,
        strict=strict,
        calendar_name=calendar_name,
    )


def load_sector_bars_by_year(
    *,
    base_path: str | Path,
    sector_name: str,
    year: int,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    asset_type: str | None = None,
    calendar_name: str = "NYSE",
) -> dict[str, pd.DataFrame]:
    return load_sector_bars(
        base_path=base_path,
        sector_name=sector_name,
        year=year,
        target_freq=target_freq,
        strict=strict,
        asset_type=asset_type,
        calendar_name=calendar_name,
    )


def load_macro_bars_by_year(
    *,
    base_path: str | Path,
    year: int,
    target_freq: BarFrequency | None = None,
    strict: bool = True,
    calendar_name: str = "NYSE",
) -> dict[str, pd.DataFrame]:
    return load_macro_bars(
        base_path=base_path,
        year=year,
        target_freq=target_freq,
        strict=strict,
        calendar_name=calendar_name,
    )