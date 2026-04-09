from __future__ import annotations

import numpy as np
import pandas as pd

from quant.indicator_names import (
    COL_BOLL_LOWER,
    COL_BOLL_MID,
    COL_BOLL_UPPER,
    COL_BOLL_WIDTH,
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_HL_RANGE,
    COL_LOG_RETURN_1D,
    COL_LOW,
    COL_MACD_DEA,
    COL_MACD_DIFF,
    COL_MACD_HIST,
    COL_OC_CHANGE,
    COL_OPEN,
    COL_VOLUME,
    atr_col,
    avg_volume_col,
    ema_col,
    highest_high_col,
    lowest_low_col,
    ma_col,
    return_col,
    rolling_std_col,
    rsi_col,
)
from quant.indicator_params import (
    ATR_WINDOWS,
    AVG_VOLUME_WINDOWS,
    BOLL_NUM_STD,
    BOLL_WINDOW,
    EMA_WINDOWS,
    HIGH_LOW_WINDOWS,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MA_WINDOWS,
    RETURN_WINDOWS,
    ROLLING_STD_WINDOWS,
    RSI_WINDOWS,
)
from quant.utils import safe_log


__all__ = [
    "build_primitive_feature_series",
    "build_primitive_snapshot",
]


REQUIRED_COLUMNS = {
    COL_DATE,
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
}


def build_primitive_feature_series(df: pd.DataFrame) -> pd.DataFrame:
    out = _validate_input(df)

    out = _add_ma_indicators(out)
    out = _add_ema_indicators(out)
    out = _add_rsi_indicators(out)
    out = _add_macd_indicators(out)
    out = _add_atr_indicators(out)
    out = _add_rolling_std_indicators(out)
    out = _add_bollinger_indicators(out)
    out = _add_high_low_indicators(out)
    out = _add_return_indicators(out)
    out = _add_price_shape_indicators(out)
    out = _add_volume_indicators(out)

    return out

    
def build_primitive_snapshot(
    df: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    out = build_primitive_feature_series(df)

    if out.empty:
        return out.copy()

    if as_of is not None:
        as_of_ts = pd.to_datetime(as_of)
        out = out[out[COL_DATE] == as_of_ts]
        return out.reset_index(drop=True)

    return out.iloc[[-1]].reset_index(drop=True)

def _validate_input(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df.copy()
    out[COL_DATE] = pd.to_datetime(out[COL_DATE])
    out = out.sort_values(COL_DATE).reset_index(drop=True)
    return out


def _add_ma_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in MA_WINDOWS:
        out[ma_col(w)] = out[COL_CLOSE].rolling(window=w, min_periods=w).mean()
    return out


def _add_ema_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in EMA_WINDOWS:
        out[ema_col(w)] = out[COL_CLOSE].ewm(span=w, adjust=False, min_periods=w).mean()
    return out


def _compute_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _add_rsi_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in RSI_WINDOWS:
        out[rsi_col(w)] = _compute_rsi(out[COL_CLOSE], w)
    return out


def _add_macd_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ema_fast = out[COL_CLOSE].ewm(span=MACD_FAST, adjust=False, min_periods=MACD_FAST).mean()
    ema_slow = out[COL_CLOSE].ewm(span=MACD_SLOW, adjust=False, min_periods=MACD_SLOW).mean()

    out[COL_MACD_DIFF] = ema_fast - ema_slow
    out[COL_MACD_DEA] = out[COL_MACD_DIFF].ewm(
        span=MACD_SIGNAL,
        adjust=False,
        min_periods=MACD_SIGNAL,
    ).mean()
    out[COL_MACD_HIST] = out[COL_MACD_DIFF] - out[COL_MACD_DEA]
    return out


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df[COL_CLOSE].shift(1)
    hl = df[COL_HIGH] - df[COL_LOW]
    hc = (df[COL_HIGH] - prev_close).abs()
    lc = (df[COL_LOW] - prev_close).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def _add_atr_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    tr = _true_range(out)
    for w in ATR_WINDOWS:
        out[atr_col(w)] = tr.ewm(alpha=1 / w, adjust=False, min_periods=w).mean()
    return out


def _add_rolling_std_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    daily_return = out[COL_CLOSE].pct_change()
    for w in ROLLING_STD_WINDOWS:
        out[rolling_std_col(w)] = daily_return.rolling(window=w, min_periods=w).std()
    return out


def _add_bollinger_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    mid = out[COL_CLOSE].rolling(window=BOLL_WINDOW, min_periods=BOLL_WINDOW).mean()
    std = out[COL_CLOSE].rolling(window=BOLL_WINDOW, min_periods=BOLL_WINDOW).std()

    out[COL_BOLL_MID] = mid
    out[COL_BOLL_UPPER] = mid + BOLL_NUM_STD * std
    out[COL_BOLL_LOWER] = mid - BOLL_NUM_STD * std
    out[COL_BOLL_WIDTH] = out[COL_BOLL_UPPER] - out[COL_BOLL_LOWER]
    return out


def _add_high_low_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in HIGH_LOW_WINDOWS:
        out[highest_high_col(w)] = out[COL_HIGH].rolling(window=w, min_periods=w).max()
        out[lowest_low_col(w)] = out[COL_LOW].rolling(window=w, min_periods=w).min()
    return out


def _add_return_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in RETURN_WINDOWS:
        out[return_col(w)] = out[COL_CLOSE].pct_change(periods=w)

    out[COL_LOG_RETURN_1D] = safe_log(out[COL_CLOSE]).diff(1)
    return out


def _add_price_shape_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_HL_RANGE] = out[COL_HIGH] - out[COL_LOW]
    out[COL_OC_CHANGE] = out[COL_CLOSE] - out[COL_OPEN]
    return out


def _add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in AVG_VOLUME_WINDOWS:
        out[avg_volume_col(w)] = out[COL_VOLUME].rolling(window=w, min_periods=w).mean()
    return out