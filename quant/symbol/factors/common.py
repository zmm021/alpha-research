from __future__ import annotations

import pandas as pd


def require_indicator_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required indicator columns for symbol factors: {missing}")


def require_factor_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required factor columns for symbol contexts: {missing}")


def safe_sign(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))