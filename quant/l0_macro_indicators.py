from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from quant.utils import (
    align_to_calendar,
    coerce_daily_frame,
    log_return,
    rolling_zscore,
)


__all__ = [
    "MacroConfig",
    "build_macro_feature_series",
    "build_macro_snapshot",
]


COL_MROC_Z = "mroc_z"
COL_RISK_ON = "risk_on"
COL_RISK_OFF = "risk_off"
COL_SPY_TREND_Z = "spy_trend_z"
COL_SPY_ABOVE_200 = "spy_above_200"
COL_SPY_TLT_RA_Z = "spy_tlt_ra_z"
COL_VIX_Z = "vix_z"
COL_VIX_SHOCK_Z = "vix_shock_z"
COL_HIGH_VOL = "high_vol"
COL_USD_STRENGTH_Z = "usd_strength_z"
COL_INFLATION_PRESSURE_Z = "inflation_pressure_z"
COL_HY_OAS_Z = "hy_oas_z"
COL_HY_OAS_SHOCK_Z = "hy_oas_shock_z"
COL_CREDIT_STRESS = "credit_stress"
COL_DATA_QUALITY_OK = "data_quality_ok"


@dataclass(frozen=True)
class MacroConfig:
    ret_horizon: int = 63
    z_window: int = 252

    trend_ma_fast: int = 50
    trend_ma_slow: int = 200
    trend_mom: int = 21

    shock_days: int = 5
    max_ffill_days: int = 3

    risk_on_threshold: float = 0.5
    risk_off_threshold: float = -0.5
    high_vol_threshold: float = 1.0
    credit_stress_threshold: float = 1.0

    clip_z: float = 4.0

    w_eq: float = 0.30
    w_ra: float = 0.25
    w_vix: float = -0.20
    w_usd: float = -0.10
    w_gold: float = -0.05
    w_oil: float = 0.05
    w_credit: float = -0.05


def build_macro_feature_series(
    daily: Mapping[str, pd.DataFrame],
    *,
    config: MacroConfig = MacroConfig(), 
    calendar_series: str = "SPY",
) -> pd.DataFrame:
    """
    Build L0 macro indicators from daily input series.

    Required keys:
    - SPY
    - TLT
    - GLD
    - VIXCLS
    - DTWEXBGS
    - DCOILWTICO

    Optional key:
    - BAMLH0A0HYM2
    """
    _validate_required_series(
        daily,
        required_keys=("SPY", "TLT", "GLD", "VIXCLS", "DTWEXBGS", "DCOILWTICO"),
    )

    cal = _get_calendar_index(daily, calendar_series=calendar_series)

    spy = _get_aligned_close(daily, "SPY", cal, config.max_ffill_days)
    tlt = _get_aligned_close(daily, "TLT", cal, config.max_ffill_days)
    gld = _get_aligned_close(daily, "GLD", cal, config.max_ffill_days)
    vix = _get_aligned_close(daily, "VIXCLS", cal, config.max_ffill_days)
    usd = _get_aligned_close(daily, "DTWEXBGS", cal, config.max_ffill_days)
    wti = _get_aligned_close(daily, "DCOILWTICO", cal, config.max_ffill_days)

    hy_oas = None
    if "BAMLH0A0HYM2" in daily:
        hy_oas = _get_aligned_close(daily, "BAMLH0A0HYM2", cal, config.max_ffill_days)

    eq_z, ra_z, vix_z, usd_z, oil_z, gold_z, cred_component_z = _compute_mroc_components(
        spy=spy,
        tlt=tlt,
        gld=gld,
        vix=vix,
        usd=usd,
        wti=wti,
        hy_oas=hy_oas,
        config=config,
    )

    mroc_z = _compute_mroc(
        eq_z=eq_z,
        ra_z=ra_z,
        vix_z=vix_z,
        usd_z=usd_z,
        oil_z=oil_z,
        gold_z=gold_z,
        cred_z=cred_component_z,
        config=config,
    )

    spy_trend_z, spy_above_200 = _compute_spy_trend(spy=spy, config=config)
    spy_tlt_ra_z = ra_z
    vix_shock_z, high_vol = _compute_vol_stress(vix=vix, vix_z=vix_z, config=config)
    usd_strength_z = usd_z
    inflation_pressure_z = _compute_inflation_pressure(wti=wti, gld=gld, config=config)
    hy_oas_z, hy_oas_shock_z, credit_stress = _compute_credit_stress(
        hy_oas=hy_oas,
        calendar=cal,
        config=config,
    )

    required_ok = (
        spy.notna()
        & tlt.notna()
        & gld.notna()
        & vix.notna()
        & usd.notna()
        & wti.notna()
    )

    out = pd.DataFrame(
        {
            "date": cal,
            COL_MROC_Z: mroc_z,
            COL_RISK_ON: mroc_z > config.risk_on_threshold,
            COL_RISK_OFF: mroc_z < config.risk_off_threshold,
            COL_SPY_TREND_Z: spy_trend_z,
            COL_SPY_ABOVE_200: spy_above_200,
            COL_SPY_TLT_RA_Z: spy_tlt_ra_z,
            COL_VIX_Z: vix_z,
            COL_VIX_SHOCK_Z: vix_shock_z,
            COL_HIGH_VOL: high_vol,
            COL_USD_STRENGTH_Z: usd_strength_z,
            COL_INFLATION_PRESSURE_Z: inflation_pressure_z,
            COL_HY_OAS_Z: hy_oas_z,
            COL_HY_OAS_SHOCK_Z: hy_oas_shock_z,
            COL_CREDIT_STRESS: credit_stress,
            COL_DATA_QUALITY_OK: required_ok,
        }
    )

    return out.reset_index(drop=True)


def build_macro_snapshot(
    daily: Mapping[str, pd.DataFrame],
    *,
    config: MacroConfig = MacroConfig(),
    calendar_series: str = "SPY",
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    out = build_macro_feature_series(
        daily,
        config=config,
        calendar_series=calendar_series,
    )

    if out.empty:
        return out.copy()

    if as_of is not None:
        as_of_ts = pd.to_datetime(as_of)
        out = out[out["date"] == as_of_ts]
        return out.reset_index(drop=True)

    return out.iloc[[-1]].reset_index(drop=True)

def _validate_required_series(
    daily: Mapping[str, pd.DataFrame],
    *,
    required_keys: tuple[str, ...],
) -> None:
    missing = [k for k in required_keys if k not in daily]
    if missing:
        raise ValueError(f"Missing required macro series: {missing}")


def _get_calendar_index(
    daily: Mapping[str, pd.DataFrame],
    *,
    calendar_series: str,
) -> pd.DatetimeIndex:
    if calendar_series not in daily:
        raise ValueError(f"calendar_series '{calendar_series}' not found in input daily map")
    return coerce_daily_frame(daily[calendar_series]).index


def _get_close_series(daily: Mapping[str, pd.DataFrame], key: str) -> pd.Series:
    df = coerce_daily_frame(daily[key])
    if "close" not in df.columns:
        raise ValueError(f"{key} missing required column 'close'")
    return df["close"].astype(float)


def _get_aligned_close(
    daily: Mapping[str, pd.DataFrame],
    key: str,
    calendar: pd.DatetimeIndex,
    max_ffill_days: int,
) -> pd.Series:
    s = _get_close_series(daily, key)
    return align_to_calendar(calendar, s, max_ffill=max_ffill_days)


def _compute_mroc_components(
    *,
    spy: pd.Series,
    tlt: pd.Series,
    gld: pd.Series,
    vix: pd.Series,
    usd: pd.Series,
    wti: pd.Series,
    hy_oas: pd.Series | None,
    config: MacroConfig,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    eq63 = log_return(spy, periods=config.ret_horizon)
    ra63 = log_return(spy / tlt, periods=config.ret_horizon)
    usd63 = log_return(usd, periods=config.ret_horizon)
    oil63 = log_return(wti, periods=config.ret_horizon)
    gold_rel63 = log_return(gld / spy, periods=config.ret_horizon)

    eq_z = rolling_zscore(eq63, window=config.z_window).clip(-config.clip_z, config.clip_z)
    ra_z = rolling_zscore(ra63, window=config.z_window).clip(-config.clip_z, config.clip_z)
    vix_z = rolling_zscore(vix, window=config.z_window).clip(-config.clip_z, config.clip_z)
    usd_z = rolling_zscore(usd63, window=config.z_window).clip(-config.clip_z, config.clip_z)
    oil_z = rolling_zscore(oil63, window=config.z_window).clip(-config.clip_z, config.clip_z)
    gold_z = rolling_zscore(gold_rel63, window=config.z_window).clip(-config.clip_z, config.clip_z)

    if hy_oas is not None:
        cred_z = rolling_zscore(hy_oas, window=config.z_window).clip(-config.clip_z, config.clip_z)
    else:
        cred_z = pd.Series(0.0, index=spy.index, dtype=float)

    return eq_z, ra_z, vix_z, usd_z, oil_z, gold_z, cred_z


def _compute_mroc(
    *,
    eq_z: pd.Series,
    ra_z: pd.Series,
    vix_z: pd.Series,
    usd_z: pd.Series,
    oil_z: pd.Series,
    gold_z: pd.Series,
    cred_z: pd.Series,
    config: MacroConfig,
) -> pd.Series:
    mroc = (
        config.w_eq * eq_z
        + config.w_ra * ra_z
        + config.w_vix * vix_z
        + config.w_usd * usd_z
        + config.w_gold * gold_z
        + config.w_oil * oil_z
        + config.w_credit * cred_z
    )
    return mroc.clip(-config.clip_z, config.clip_z)


def _compute_spy_trend(
    *,
    spy: pd.Series,
    config: MacroConfig,
) -> tuple[pd.Series, pd.Series]:
    ma50 = spy.rolling(
        window=config.trend_ma_fast,
        min_periods=max(10, config.trend_ma_fast // 3),
    ).mean()
    ma200 = spy.rolling(
        window=config.trend_ma_slow,
        min_periods=max(20, config.trend_ma_slow // 3),
    ).mean()

    dist50 = spy / ma50 - 1.0
    dist200 = spy / ma200 - 1.0
    mom = log_return(spy, periods=config.trend_mom)

    trend_z = (
        0.50 * rolling_zscore(dist200, window=config.z_window)
        + 0.25 * rolling_zscore(dist50, window=config.z_window)
        + 0.25 * rolling_zscore(mom, window=config.z_window)
    ).clip(-config.clip_z, config.clip_z)

    return trend_z, (spy > ma200)


def _compute_vol_stress(
    *,
    vix: pd.Series,
    vix_z: pd.Series,
    config: MacroConfig,
) -> tuple[pd.Series, pd.Series]:
    vix_shock = log_return(vix, periods=config.shock_days)
    vix_shock_z = rolling_zscore(vix_shock, window=config.z_window).clip(-config.clip_z, config.clip_z)
    high_vol = vix_z > config.high_vol_threshold
    return vix_shock_z, high_vol


def _compute_inflation_pressure(
    *,
    wti: pd.Series,
    gld: pd.Series,
    config: MacroConfig,
) -> pd.Series:
    oil63 = log_return(wti, periods=config.ret_horizon)
    gold63 = log_return(gld, periods=config.ret_horizon)

    inflation_z = (
        0.70 * rolling_zscore(oil63, window=config.z_window)
        + 0.30 * rolling_zscore(gold63, window=config.z_window)
    )
    return inflation_z.clip(-config.clip_z, config.clip_z)


def _compute_credit_stress(
    *,
    hy_oas: pd.Series | None,
    calendar: pd.DatetimeIndex,
    config: MacroConfig,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if hy_oas is None:
        empty = pd.Series(index=calendar, dtype=float)
        credit_stress = pd.Series(False, index=calendar, dtype=bool)
        return empty, empty.copy(), credit_stress

    hy_oas_z = rolling_zscore(hy_oas, window=config.z_window).clip(-config.clip_z, config.clip_z)
    hy_oas_shock = hy_oas.diff(config.shock_days)
    hy_oas_shock_z = rolling_zscore(hy_oas_shock, window=config.z_window).clip(-config.clip_z, config.clip_z)
    credit_stress = hy_oas_z > config.credit_stress_threshold
    return hy_oas_z, hy_oas_shock_z, credit_stress