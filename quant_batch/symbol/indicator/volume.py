from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators


def compute_volume_indicators(
    df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    volume_window = int(config["volume_window"])

    volume = df[Fields.VOLUME]
    out = pd.DataFrame(index=df.index)

    avg_volume = volume.rolling(
        window=volume_window,
        min_periods=volume_window,
    ).mean()

    out[Indicators.VOLUME_RATIO] = volume / avg_volume.replace(0, pd.NA)

    return out