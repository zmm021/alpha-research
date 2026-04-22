from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def compute_trend_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    ma_short_window = int(config["ma_short_window"])
    ma_long_window = int(config["ma_long_window"])

    close = df[Fields.CLOSE]

    out = pd.DataFrame(index=df.index)

    ma20 = close.rolling(
        window=ma_short_window,
        min_periods=ma_short_window,
    ).mean()

    ma50 = close.rolling(
        window=ma_long_window,
        min_periods=ma_long_window,
    ).mean()

    out[Indicators.MA20] = ma20
    out[Indicators.MA50] = ma50
    out[Indicators.MA20_SLOPE] = ma20.diff()
    out[Indicators.MA50_SLOPE] = ma50.diff()
    return out