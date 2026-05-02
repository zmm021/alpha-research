from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def _compute_range_position(
    *,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    high_window: int,
    range_position_window: int,
    distance_col: str,
    range_low_col: str,
    range_high_col: str,
    range_position_col: str,
) -> pd.DataFrame:
    out = pd.DataFrame(index=close.index)

    rolling_high = high.rolling(
        window=high_window,
        min_periods=high_window,
    ).max()

    out[distance_col] = (rolling_high - close) / close.replace(0, pd.NA)

    range_low = low.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).min()

    range_high = high.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).max()

    range_width = (range_high - range_low).replace(0, pd.NA)

    out[range_low_col] = range_low
    out[range_high_col] = range_high
    out[range_position_col] = ((close - range_low) / range_width).clip(
        lower=0.0,
        upper=1.0,
    )

    return out


def compute_position_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    close = df[Fields.CLOSE]
    high = df[Fields.HIGH]
    low = df[Fields.LOW]

    high_window_short = int(config["high_window_short"])
    range_position_window_short = int(config["range_position_window_short"])

    high_window_mid = int(config["high_window_mid"])
    range_position_window_mid = int(config["range_position_window_mid"])

    short_df = _compute_range_position(
        close=close,
        high=high,
        low=low,
        high_window=high_window_short,
        range_position_window=range_position_window_short,
        distance_col=Indicators.DISTANCE_TO_HIGH_SHORT,
        range_low_col=Indicators.RANGE_LOW_SHORT,
        range_high_col=Indicators.RANGE_HIGH_SHORT,
        range_position_col=Indicators.RANGE_POSITION_SHORT,
    )

    mid_df = _compute_range_position(
        close=close,
        high=high,
        low=low,
        high_window=high_window_mid,
        range_position_window=range_position_window_mid,
        distance_col=Indicators.DISTANCE_TO_HIGH_MID,
        range_low_col=Indicators.RANGE_LOW_MID,
        range_high_col=Indicators.RANGE_HIGH_MID,
        range_position_col=Indicators.RANGE_POSITION_MID,
    )

    return short_df.join(mid_df)