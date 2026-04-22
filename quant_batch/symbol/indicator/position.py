from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def compute_position_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    high_window = int(config["high_window"])
    range_position_window = int(config["range_position_window"])

    close = df[Fields.CLOSE]
    high = df[Fields.HIGH]
    low = df[Fields.LOW]

    out = pd.DataFrame(index=df.index)

    rolling_high = high.rolling(
        window=high_window,
        min_periods=high_window,
    ).max()

    out[Indicators.DISTANCE_TO_HIGH] = (
        (rolling_high - close) / close.replace(0, pd.NA)
    )

    range_low = low.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).min()

    range_high = high.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).max()

    range_width = (range_high - range_low).replace(0, pd.NA)

    out[Indicators.RANGE_LOW] = range_low
    out[Indicators.RANGE_HIGH] = range_high
    out[Indicators.RANGE_POSITION] = (
        (close - range_low) / range_width
    ).clip(lower=0.0, upper=1.0)

    return out