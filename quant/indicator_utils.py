from __future__ import annotations

import numpy as np
import pandas as pd


def coerce_daily_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"])
        out = out.set_index("date")
    else:
        out.index = pd.to_datetime(out.index)

    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_convert("America/New_York").tz_localize(None)

    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out.index.name = "date"
    return out


def align_to_calendar(
    calendar: pd.DatetimeIndex,
    s: pd.Series,
    max_ffill: int = 3,
) -> pd.Series:
    return s.reindex(calendar).ffill(limit=max_ffill)


def safe_log(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    return np.log(s.where(s > 0.0))


def log_return(s: pd.Series, periods: int = 1) -> pd.Series:
    return safe_log(s).diff(periods)


def rolling_zscore(
    s: pd.Series,
    window: int,
    min_periods: int | None = None,
    eps: float = 1e-9,
) -> pd.Series:
    if min_periods is None:
        min_periods = max(10, window // 3)
    mu = s.rolling(window=window, min_periods=min_periods).mean()
    sd = s.rolling(window=window, min_periods=min_periods).std(ddof=0)
    return (s - mu) / (sd + eps)