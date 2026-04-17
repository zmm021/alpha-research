from __future__ import annotations

from enum import Enum
from typing import Final

import pandas as pd


# =========================
# Canonical Bar Columns
# =========================

COL_DATE: Final[str] = "date"
COL_OPEN: Final[str] = "open"
COL_HIGH: Final[str] = "high"
COL_LOW: Final[str] = "low"
COL_CLOSE: Final[str] = "close"
COL_VOLUME: Final[str] = "volume"


# =========================
# Frequency Enum
# =========================

class BarFrequency(str, Enum):
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1h"
    DAY_1 = "1d"


_PANDAS_FREQ_MAP: dict[BarFrequency, str] = {
    BarFrequency.MIN_1: "1min",
    BarFrequency.MIN_5: "5min",
    BarFrequency.MIN_15: "15min",
    BarFrequency.MIN_30: "30min",
    BarFrequency.HOUR_1: "1h",
    BarFrequency.DAY_1: "1D",
}


# =========================
# Helpers
# =========================

def _require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _ensure_datetime_col(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if date_col not in df.columns:
        raise ValueError(f"Missing datetime column: {date_col}")

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], utc=True, errors="coerce")

    if out[date_col].isna().any():
        raise ValueError(f"Failed to parse some datetime values in column: {date_col}")

    return out


# =========================
# Public APIs
# =========================

def infer_session_date(
    df: pd.DataFrame,
    *,
    date_col: str = COL_DATE,
    output_col: str = "session_date",
) -> pd.DataFrame:
    """
    Add a session_date column from datetime column.
    Useful before intraday aggregation.
    """
    out = _ensure_datetime_col(df, date_col)
    out[output_col] = out[date_col].dt.strftime("%Y-%m-%d")
    return out


def aggregate_ohlcv_bars(
    df: pd.DataFrame,
    *,
    target_freq: BarFrequency,
    date_col: str = COL_DATE,
    session_col: str = "session_date",
    keep_partial_last_bar: bool = True,
) -> pd.DataFrame:
    """
    Aggregate lower-frequency OHLCV bars from raw/intraday bars.

    Required columns:
      - date
      - open
      - high
      - low
      - close
      - volume

    Notes:
    - For intraday aggregation, aggregation is done within each session_date.
    - For daily aggregation, session_col is not required.
    """
    _require_columns(
        df,
        [date_col, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME],
        "aggregate_ohlcv_bars input",
    )

    if target_freq not in _PANDAS_FREQ_MAP:
        raise ValueError(f"Unsupported target frequency: {target_freq}")

    out = _ensure_datetime_col(df, date_col).copy()
    out = out.sort_values(date_col).reset_index(drop=True)

    pandas_freq = _PANDAS_FREQ_MAP[target_freq]

    # =========================
    # Daily bars
    # =========================
    if target_freq == BarFrequency.DAY_1:
        grouped = (
            out.set_index(date_col)
            .resample(pandas_freq)
            .agg(
                {
                    COL_OPEN: "first",
                    COL_HIGH: "max",
                    COL_LOW: "min",
                    COL_CLOSE: "last",
                    COL_VOLUME: "sum",
                }
            )
            .dropna(subset=[COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE])
            .reset_index()
        )
        return grouped

    # =========================
    # Intraday bars
    # =========================
    if session_col not in out.columns:
        raise ValueError(
            f"session_col '{session_col}' not found. "
            f"Run infer_session_date(...) before aggregation."
        )

    frames: list[pd.DataFrame] = []

    for session_value, session_df in out.groupby(session_col, sort=True):
        session_df = session_df.sort_values(date_col).copy()

        agg_df = (
            session_df.set_index(date_col)
            .resample(
                pandas_freq,
                label="right",
                closed="right",
            )
            .agg(
                {
                    COL_OPEN: "first",
                    COL_HIGH: "max",
                    COL_LOW: "min",
                    COL_CLOSE: "last",
                    COL_VOLUME: "sum",
                }
            )
            .dropna(subset=[COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE])
            .reset_index()
        )

        if not keep_partial_last_bar and not agg_df.empty:
            last_ts = session_df[date_col].max()
            expected_end = agg_df[date_col].iloc[-1]
            if expected_end > last_ts:
                agg_df = agg_df.iloc[:-1]

        agg_df[session_col] = session_value
        frames.append(agg_df)

    if not frames:
        return pd.DataFrame(columns=[date_col, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME, session_col])

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(date_col).reset_index(drop=True)
    return result