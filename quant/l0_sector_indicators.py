from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from quant.utils import (
    align_to_calendar,
    coerce_daily_frame,
    log_return,
    rolling_zscore,
)


__all__ = ["SectorConfig", "build_sector_indicators"]


COL_SECTOR = "sector"
COL_SECTOR_ETF = "sector_etf"
COL_RS63_Z = "rs63_z"
COL_RS_ACCEL_Z = "rs_accel_z"
COL_VOL_RATIO_Z = "vol_ratio_z"
COL_ETF_VOLUME_ACTIVITY_Z = "etf_volume_activity_z"
COL_BREADTH_FRAC = "breadth_frac"
COL_BREADTH_PCTILE = "breadth_pctile"
COL_DISPERSION_Z = "dispersion_z"
COL_LEADER_CONCENTRATION_Z = "leader_concentration_z"
COL_N_MEMBERS_TOTAL = "n_members_total"
COL_N_MEMBERS_VALID = "n_members_valid"
COL_DATA_QUALITY_OK = "data_quality_ok"


@dataclass(frozen=True)
class SectorConfig:
    rs_short: int = 20
    rs_long: int = 63
    z_window: int = 252
    vol_window: int = 20
    breadth_ma: int = 20
    min_members: int = 5
    max_ffill_days: int = 3
    clip_z: float = 4.0


def build_sector_feature_series(
    daily: Mapping[str, pd.DataFrame],
    *,
    sector_to_etf: Mapping[str, str],
    sector_to_members: Mapping[str, Sequence[str]],
    benchmark: str = "SPY",
    config: SectorConfig = SectorConfig(),
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Build L0 sector indicators from daily input series.

    Returns one row per (date, sector).
    """
    if benchmark not in daily:
        raise ValueError(f"Missing benchmark series: {benchmark}")

    cal = coerce_daily_frame(daily[benchmark]).index
    spy = _get_aligned_close(daily, benchmark, cal, config.max_ffill_days)

    rows: list[pd.DataFrame] = []

    for sector, etf in sector_to_etf.items():
        if etf not in daily:
            raise ValueError(f"Missing sector ETF '{etf}' for sector '{sector}'")

        etf_close = _get_aligned_close(daily, etf, cal, config.max_ffill_days)
        etf_volume = _get_aligned_volume(daily, etf, cal, config.max_ffill_days)

        rs63_z, rs_accel_z = _compute_relative_strength(
            etf_close=etf_close,
            spy=spy,
            config=config,
        )

        vol_ratio_z = _compute_vol_ratio(
            etf_close=etf_close,
            spy=spy,
            config=config,
        )

        etf_volume_activity_z = _compute_etf_volume_activity(
            etf_volume=etf_volume,
            config=config,
        )

        breadth_frac, breadth_pctile, dispersion_z, leader_concentration_z, n_members_valid = (
            _compute_internal_sector_structure(
                daily=daily,
                calendar=cal,
                members=sector_to_members.get(sector, []),
                config=config,
            )
        )

        data_quality_ok = (
            etf_close.notna()
            & spy.notna()
            & (n_members_valid >= config.min_members)
        )

        df_sector = pd.DataFrame(
            {
                "date": cal,
                COL_SECTOR: sector,
                COL_SECTOR_ETF: etf,
                COL_RS63_Z: rs63_z,
                COL_RS_ACCEL_Z: rs_accel_z,
                COL_VOL_RATIO_Z: vol_ratio_z,
                COL_ETF_VOLUME_ACTIVITY_Z: etf_volume_activity_z,
                COL_BREADTH_FRAC: breadth_frac,
                COL_BREADTH_PCTILE: breadth_pctile,
                COL_DISPERSION_Z: dispersion_z,
                COL_LEADER_CONCENTRATION_Z: leader_concentration_z,
                COL_N_MEMBERS_TOTAL: len(sector_to_members.get(sector, [])),
                COL_N_MEMBERS_VALID: n_members_valid,
                COL_DATA_QUALITY_OK: data_quality_ok,
            }
        )
        rows.append(df_sector)

    out = pd.concat(rows, ignore_index=True)

    if as_of is not None:
        as_of_ts = pd.to_datetime(as_of)
        out = out[out["date"] == as_of_ts]

    return out.reset_index(drop=True)


def _get_close_series(daily: Mapping[str, pd.DataFrame], key: str) -> pd.Series:
    df = coerce_daily_frame(daily[key])
    if "close" not in df.columns:
        raise ValueError(f"{key} missing required column 'close'")
    return df["close"].astype(float)


def _get_volume_series(daily: Mapping[str, pd.DataFrame], key: str) -> pd.Series:
    df = coerce_daily_frame(daily[key])
    if "volume" not in df.columns:
        raise ValueError(f"{key} missing required column 'volume'")
    return df["volume"].astype(float)


def _get_aligned_close(
    daily: Mapping[str, pd.DataFrame],
    key: str,
    calendar: pd.DatetimeIndex,
    max_ffill_days: int,
) -> pd.Series:
    s = _get_close_series(daily, key)
    return align_to_calendar(calendar, s, max_ffill=max_ffill_days)


def _get_aligned_volume(
    daily: Mapping[str, pd.DataFrame],
    key: str,
    calendar: pd.DatetimeIndex,
    max_ffill_days: int,
) -> pd.Series:
    s = _get_volume_series(daily, key)
    return align_to_calendar(calendar, s, max_ffill=max_ffill_days)


def _compute_relative_strength(
    *,
    etf_close: pd.Series,
    spy: pd.Series,
    config: SectorConfig,
) -> tuple[pd.Series, pd.Series]:
    rs_long = log_return(etf_close, periods=config.rs_long) - log_return(spy, periods=config.rs_long)
    rs_short = log_return(etf_close, periods=config.rs_short) - log_return(spy, periods=config.rs_short)

    rs63_z = rolling_zscore(rs_long, window=config.z_window).clip(-config.clip_z, config.clip_z)
    rs_accel_z = rolling_zscore(rs_short - rs_long, window=config.z_window).clip(-config.clip_z, config.clip_z)

    return rs63_z, rs_accel_z


def _compute_vol_ratio(
    *,
    etf_close: pd.Series,
    spy: pd.Series,
    config: SectorConfig,
) -> pd.Series:
    r_etf = log_return(etf_close, periods=1)
    r_spy = log_return(spy, periods=1)

    vol_etf = r_etf.rolling(
        window=config.vol_window,
        min_periods=max(10, config.vol_window // 2),
    ).std(ddof=0)
    vol_spy = r_spy.rolling(
        window=config.vol_window,
        min_periods=max(10, config.vol_window // 2),
    ).std(ddof=0)

    ratio = np.log((vol_etf + 1e-9) / (vol_spy + 1e-9))
    return rolling_zscore(ratio, window=config.z_window).clip(-config.clip_z, config.clip_z)


def _compute_etf_volume_activity(
    *,
    etf_volume: pd.Series,
    config: SectorConfig,
) -> pd.Series:
    lv = np.log(etf_volume.clip(lower=1.0))
    volume_deviation = lv - lv.rolling(window=config.vol_window, min_periods=max(10, config.vol_window // 2)).mean()
    return rolling_zscore(volume_deviation, window=config.z_window).clip(-config.clip_z, config.clip_z)


def _compute_internal_sector_structure(
    *,
    daily: Mapping[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    members: Sequence[str],
    config: SectorConfig,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    available_members = [m for m in members if m in daily]

    if not available_members:
        empty = pd.Series(index=calendar, dtype=float)
        n_valid = pd.Series(0, index=calendar, dtype=int)
        return empty, empty.copy(), empty.copy(), empty.copy(), n_valid

    member_close_series: list[pd.Series] = []
    for member in available_members:
        s = _get_aligned_close(daily, member, calendar, config.max_ffill_days)
        member_close_series.append(s.rename(member))

    px = pd.concat(member_close_series, axis=1)
    valid_n = px.notna().sum(axis=1).astype(int)

    ma = px.rolling(
        window=config.breadth_ma,
        min_periods=max(10, config.breadth_ma // 2),
    ).mean()

    above_ma = (px > ma).astype(float)
    breadth_frac = above_ma.mean(axis=1, skipna=True)

    r_short = px.apply(lambda col: log_return(col, periods=config.rs_short))
    dispersion = r_short.std(axis=1, ddof=0)

    abs_r = r_short.abs()
    denom = abs_r.sum(axis=1).replace(0.0, np.nan)
    weights = abs_r.div(denom, axis=0)
    hhi = (weights ** 2).sum(axis=1)

    breadth_frac = breadth_frac.where(valid_n >= config.min_members)
    dispersion = dispersion.where(valid_n >= config.min_members)
    hhi = hhi.where(valid_n >= config.min_members)

    breadth_pctile = breadth_frac.rank(pct=True)
    dispersion_z = rolling_zscore(dispersion, window=config.z_window).clip(-config.clip_z, config.clip_z)
    leader_concentration_z = rolling_zscore(hhi, window=config.z_window).clip(-config.clip_z, config.clip_z)

    return breadth_frac, breadth_pctile, dispersion_z, leader_concentration_z, valid_n