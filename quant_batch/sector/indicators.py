from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields, Indicators
from quant.common.schemas import IndicatorOutput
from quant.common.types import ConfigDict


# =========================
# Helpers
# =========================

def _require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def _zscore(series: pd.Series, window: int) -> pd.Series:
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    return (series - rolling_mean) / rolling_std.replace(0, pd.NA)


def _compute_return(series: pd.Series, window: int) -> pd.Series:
    return series.pct_change(periods=window)


def _compute_volume_ratio(volume: pd.Series, window: int) -> pd.Series:
    avg_volume = volume.rolling(window=window, min_periods=window).mean()
    return volume / avg_volume.replace(0, pd.NA)


# =========================
# Core
# =========================

def compute_sector_indicators(
    sector_etf_df: pd.DataFrame,
    member_dfs: dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    """
    Compute enhanced phase-1 sector indicators.

    Output:
      - rs_z
      - rs_momentum_z
      - breadth_frac
      - breadth_momentum
      - vol_ratio_z
      - vol_trend_z
    """
    if sector_etf_df is None or sector_etf_df.empty:
        raise ValueError("sector_etf_df is empty")

    if spy_df is None or spy_df.empty:
        raise ValueError("spy_df is empty")

    if member_dfs is None or len(member_dfs) == 0:
        raise ValueError("member_dfs is empty")

    _require_columns(sector_etf_df, [Fields.CLOSE, Fields.VOLUME], "sector_etf_df")
    _require_columns(spy_df, [Fields.CLOSE], "spy_df")

    indicator_cfg = config["indicators"]

    rs_window = int(indicator_cfg["rs_window"])
    rs_z_window = int(indicator_cfg["rs_z_window"])
    rs_momentum_window = int(indicator_cfg["rs_momentum_window"])

    breadth_ma_window = int(indicator_cfg["breadth_ma_window"])
    breadth_momentum_window = int(indicator_cfg["breadth_momentum_window"])

    vol_window = int(indicator_cfg["vol_window"])
    vol_z_window = int(indicator_cfg["vol_z_window"])
    vol_trend_window = int(indicator_cfg["vol_trend_window"])

    out = pd.DataFrame(index=sector_etf_df.index)

    sector_close = sector_etf_df[Fields.CLOSE]
    sector_volume = sector_etf_df[Fields.VOLUME]
    spy_close = spy_df[Fields.CLOSE].reindex(out.index)

    # =========================
    # 1. Relative Strength
    # =========================
    sector_ret = _compute_return(sector_close, rs_window)
    spy_ret = _compute_return(spy_close, rs_window)

    rs_raw = sector_ret - spy_ret
    out[Indicators.RS_Z] = _zscore(rs_raw, rs_z_window)
    out[Indicators.RS_MOMENTUM_Z] = _zscore(
        rs_raw.diff(rs_momentum_window),
        rs_z_window,
    )

    # =========================
    # 2. Breadth
    # =========================
    member_flags: list[pd.Series] = []

    for symbol, df in member_dfs.items():
        if df is None or df.empty:
            continue
        if Fields.CLOSE not in df.columns:
            continue

        member_close = df[Fields.CLOSE].reindex(out.index)
        member_ma = member_close.rolling(
            window=breadth_ma_window,
            min_periods=breadth_ma_window,
        ).mean()

        flag = (member_close > member_ma).astype(float)
        member_flags.append(flag.rename(symbol))

    if member_flags:
        breadth_df = pd.concat(member_flags, axis=1)
        breadth_frac = breadth_df.mean(axis=1, skipna=True)
    else:
        breadth_frac = pd.Series(0.0, index=out.index)

    out[Indicators.BREADTH_FRAC] = breadth_frac
    out[Indicators.BREADTH_MOMENTUM] = breadth_frac.diff(breadth_momentum_window)

    # =========================
    # 3. Volume / Participation
    # =========================
    vol_ratio = _compute_volume_ratio(sector_volume, vol_window)

    out[Indicators.VOL_RATIO_Z] = _zscore(vol_ratio, vol_z_window)
    out[Indicators.VOL_TREND_Z] = _zscore(
        vol_ratio.diff(vol_trend_window),
        vol_z_window,
    )

    return out


def compute_sector_indicator_output(
    sector_etf_df: pd.DataFrame,
    member_dfs: dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    config: ConfigDict,
) -> IndicatorOutput:
    """
    Convenience helper for latest-row / snapshot usage.
    """
    indicator_df = compute_sector_indicators(
        sector_etf_df=sector_etf_df,
        member_dfs=member_dfs,
        spy_df=spy_df,
        config=config,
    )
    latest = indicator_df.iloc[-1].dropna().to_dict()
    return IndicatorOutput(values={k: float(v) for k, v in latest.items()})