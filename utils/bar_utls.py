from __future__ import annotations

from enum import Enum
from typing import Iterable

import pandas as pd

from quant.indicator_names import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
)


class BarFrequency(str, Enum):
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1h"
    DAY_1 = "1d"


DEFAULT_OHLCV_COLUMNS = (
    COL_DATE,
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
)


def aggregate_ohlcv_bars(
    df: pd.DataFrame,
    *,
    target_freq: BarFrequency,
    date_col: str = COL_DATE,
    session_col: str | None = None,
    keep_partial_last_bar: bool = True,
) -> pd.DataFrame:
    """
    Aggregate a single-symbol OHLCV time series into a target bar frequency.

    Input:
    - one symbol only
    - must contain date/open/high/low/close/volume

    Output:
    - aggregated OHLCV DataFrame
    """
    out = _validate_ohlcv_input(df, date_col=date_col)
    out = out.sort_values(date_col).reset_index(drop=True)

    if session_col is not None and session_col in out.columns:
        parts = []
        for _, g in out.groupby(session_col, sort=False):
            agg = _aggregate_single_block(
                g,
                target_freq=target_freq,
                date_col=date_col,
                keep_partial_last_bar=keep_partial_last_bar,
            )
            parts.append(agg)
        if not parts:
            return _empty_ohlcv_frame()
        return pd.concat(parts, ignore_index=True)

    return _aggregate_single_block(
        out,
        target_freq=target_freq,
        date_col=date_col,
        keep_partial_last_bar=keep_partial_last_bar,
    )


def aggregate_ohlcv_bars_by_symbol(
    df: pd.DataFrame,
    *,
    symbol_col: str = "symbol",
    target_freq: BarFrequency,
    date_col: str = COL_DATE,
    session_col: str | None = None,
    keep_partial_last_bar: bool = True,
) -> pd.DataFrame:
    """
    Aggregate a multi-symbol OHLCV DataFrame.

    Required columns:
    - symbol_col
    - date/open/high/low/close/volume
    """
    if symbol_col not in df.columns:
        raise ValueError(f"Missing required symbol column: {symbol_col}")

    parts = []
    for symbol, g in df.groupby(symbol_col, sort=False):
        agg = aggregate_ohlcv_bars(
            g,
            target_freq=target_freq,
            date_col=date_col,
            session_col=session_col,
            keep_partial_last_bar=keep_partial_last_bar,
        )
        if not agg.empty:
            agg.insert(0, symbol_col, symbol)
            parts.append(agg)

    if not parts:
        return pd.DataFrame(columns=[symbol_col, *DEFAULT_OHLCV_COLUMNS])

    return pd.concat(parts, ignore_index=True)


def filter_recent_bars(
    df: pd.DataFrame,
    *,
    n_bars: int,
    date_col: str = COL_DATE,
) -> pd.DataFrame:
    """
    Keep only the most recent n bars.
    """
    if n_bars <= 0:
        raise ValueError("n_bars must be > 0")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.sort_values(date_col).reset_index(drop=True)
    return out.tail(n_bars).reset_index(drop=True)


def align_bar_window(
    df: pd.DataFrame,
    *,
    end_time: str | pd.Timestamp | None = None,
    n_bars: int | None = None,
    date_col: str = COL_DATE,
) -> pd.DataFrame:
    """
    Slice a time series up to end_time, then optionally keep only the last n bars.

    Useful for:
    - offline snapshot as_of
    - realtime rolling window
    """
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.sort_values(date_col).reset_index(drop=True)

    if end_time is not None:
        end_ts = pd.to_datetime(end_time)
        out = out[out[date_col] <= end_ts].reset_index(drop=True)

    if n_bars is not None:
        if n_bars <= 0:
            raise ValueError("n_bars must be > 0")
        out = out.tail(n_bars).reset_index(drop=True)

    return out


def infer_session_date(
    df: pd.DataFrame,
    *,
    date_col: str = COL_DATE,
    output_col: str = "session_date",
) -> pd.DataFrame:
    """
    Add a simple session_date column based on local calendar date.

    Useful when you want to aggregate intraday bars separately by trading day.
    """
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out[output_col] = out[date_col].dt.floor("D")
    return out


def _aggregate_single_block(
    df: pd.DataFrame,
    *,
    target_freq: BarFrequency,
    date_col: str,
    keep_partial_last_bar: bool,
) -> pd.DataFrame:
    if df.empty:
        return _empty_ohlcv_frame()

    rule = _to_pandas_rule(target_freq)

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.sort_values(date_col).reset_index(drop=True)
    out = out.set_index(date_col)

    agg = out.resample(
        rule=rule,
        label="right",
        closed="right",
    ).agg(
        {
            COL_OPEN: "first",
            COL_HIGH: "max",
            COL_LOW: "min",
            COL_CLOSE: "last",
            COL_VOLUME: "sum",
        }
    )

    agg = agg.dropna(subset=[COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE])

    if not keep_partial_last_bar and not agg.empty:
        last_bar_end = agg.index[-1]
        last_src_time = out.index[-1]
        if last_src_time < last_bar_end:
            agg = agg.iloc[:-1]

    return agg.reset_index()


def _validate_ohlcv_input(
    df: pd.DataFrame,
    *,
    date_col: str,
) -> pd.DataFrame:
    required = {date_col, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {sorted(missing)}")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    return out


def _to_pandas_rule(freq: BarFrequency) -> str:
    mapping = {
        BarFrequency.MIN_1: "1min",
        BarFrequency.MIN_5: "5min",
        BarFrequency.MIN_15: "15min",
        BarFrequency.MIN_30: "30min",
        BarFrequency.HOUR_1: "1h",
        BarFrequency.DAY_1: "1D",
    }
    return mapping[freq]


def _empty_ohlcv_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            COL_DATE,
            COL_OPEN,
            COL_HIGH,
            COL_LOW,
            COL_CLOSE,
            COL_VOLUME,
        ]
    )