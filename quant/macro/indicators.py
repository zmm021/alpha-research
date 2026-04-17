from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators
from quant.common.types import ConfigDict


# =========================
# Helpers
# =========================

def _require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std()
    return (series - mean) / std.replace(0, pd.NA)


def _return(series: pd.Series, window: int) -> pd.Series:
    return series.pct_change(window)


# =========================
# Core
# =========================

def compute_macro_indicators(
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    hy_oas_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:

    _require_columns(spy_df, [Fields.CLOSE], "spy_df")
    _require_columns(vix_df, [Fields.CLOSE], "vix_df")
    _require_columns(hy_oas_df, [Fields.CLOSE], "hy_oas_df")

    cfg = config["indicators"]

    spy_ret_window = cfg["spy_return_window"]
    spy_z_window = cfg["spy_z_window"]

    vix_z_window = cfg["vix_z_window"]
    credit_z_window = cfg["credit_z_window"]

    out = pd.DataFrame(index=spy_df.index)

    # ===== SPY TREND =====
    spy_ret = _return(spy_df[Fields.CLOSE], spy_ret_window)
    out[Indicators.SPY_TREND_Z] = _zscore(spy_ret, spy_z_window)

    # ===== VIX =====
    vix = vix_df[Fields.CLOSE].reindex(out.index)
    out[Indicators.VIX_Z] = _zscore(vix, vix_z_window)

    # ===== CREDIT =====
    credit = hy_oas_df[Fields.CLOSE].reindex(out.index)
    out[Indicators.HY_OAS_Z] = _zscore(credit, credit_z_window)

    return out