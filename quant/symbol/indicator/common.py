from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields


def require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def require_symbol_ohlcv(df: pd.DataFrame, name: str = "symbol_df") -> None:
    require_columns(
        df,
        [Fields.OPEN, Fields.HIGH, Fields.LOW, Fields.CLOSE, Fields.VOLUME],
        name,
    )