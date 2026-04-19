from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def _compute_atr(df: pd.DataFrame, window: int) -> pd.Series:
    prev_close = df[Fields.CLOSE].shift(1)

    high_low = df[Fields.HIGH] - df[Fields.LOW]
    high_prev_close = (df[Fields.HIGH] - prev_close).abs()
    low_prev_close = (df[Fields.LOW] - prev_close).abs()

    true_range = pd.concat(
        [high_low, high_prev_close, low_prev_close],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(window=window, min_periods=window).mean()


def compute_volatility_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    atr_window = int(config["atr_window"])

    close = df[Fields.CLOSE]
    out = pd.DataFrame(index=df.index)

    atr = _compute_atr(df, atr_window)
    out[Indicators.ATR_PCT] = atr / close.replace(0, pd.NA)

    return out