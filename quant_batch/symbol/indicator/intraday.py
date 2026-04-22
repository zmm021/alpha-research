from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def _compute_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (
        df[Fields.HIGH] + df[Fields.LOW] + df[Fields.CLOSE]
    ) / 3.0

    cum_pv = (typical_price * df[Fields.VOLUME]).cumsum()
    cum_vol = df[Fields.VOLUME].cumsum()

    return cum_pv / cum_vol.replace(0, pd.NA)


def compute_intraday_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    del config

    open_ = df[Fields.OPEN]
    close = df[Fields.CLOSE]

    out = pd.DataFrame(index=df.index)

    prev_close = close.shift(1)
    out[Indicators.GAP_PCT] = (
        (open_ - prev_close) / prev_close.replace(0, pd.NA)
    )

    vwap = _compute_vwap(df)
    out[Indicators.PRICE_VS_VWAP] = (
        (close - vwap) / vwap.replace(0, pd.NA)
    )

    return out