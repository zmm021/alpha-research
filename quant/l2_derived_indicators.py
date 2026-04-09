from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from quant.indicator_names import (
    COL_ATR_PCT,
    COL_ATR_PERCENTILE_60,
    COL_BOLL_LOWER,
    COL_BOLL_MID,
    COL_BOLL_POSITION,
    COL_BOLL_UPPER,
    COL_BOLL_WIDTH,
    COL_BOLL_WIDTH_PCT,
    COL_CHOPINESS_INDEX,
    COL_CLOSE,
    COL_DATE,
    COL_DISTANCE_TO_RECENT_HIGH,
    COL_DISTANCE_TO_RECENT_LOW,
    COL_DRAWDOWN_FROM_PEAK,
    COL_HIGH,
    COL_LIQUIDITY_SCORE,
    COL_LOW,
    COL_MA20_SLOPE,
    COL_MA50_SLOPE,
    COL_MA200_SLOPE,
    COL_MA_ALIGNMENT_BEARISH,
    COL_MA_ALIGNMENT_BULLISH,
    COL_MACD_CROSS_STATE,
    COL_MACD_DEA,
    COL_MACD_DIFF,
    COL_MACD_HIST,
    COL_MACD_TREND_STATE,
    COL_PRICE_VS_BOLL_MID,
    COL_PRICE_VS_MA20,
    COL_PRICE_VS_MA50,
    COL_PRICE_VS_MA200,
    COL_RANGE_EFFICIENCY,
    COL_REBOUND_FROM_LOW,
    COL_RSI_14,
    COL_RSI_REGIME,
    COL_RSI_STATE,
    COL_SECTOR_RETURN,
    COL_SECTOR_STRENGTH,
    COL_SPY_RETURN,
    COL_SYMBOL_VS_MARKET,
    COL_TREND_STRENGTH,
    COL_VOL_PERCENTILE_20,
    COL_VOLUME,
    COL_VOLUME_VS_AVG20,
    STATE_BEARISH,
    STATE_BULLISH,
    STATE_DEATH_CROSS,
    STATE_GOLDEN_CROSS,
    STATE_NEUTRAL,
    STATE_NONE,
    STATE_OVERBOUGHT,
    STATE_OVERSOLD,
    atr_col,
    avg_volume_col,
    highest_high_col,
    lowest_low_col,
    ma_col,
    return_col,
    rolling_std_col,
)
from quant.indicator_params import (
    ATR_PERCENTILE_WINDOW,
    CHOPINESS_WINDOW,
    LIQUIDITY_SCORE_STABILITY_WINDOW,
    LIQUIDITY_SCORE_WEIGHT_REL_VOL,
    LIQUIDITY_SCORE_WEIGHT_STABILITY,
    MA_SLOPE_WINDOW,
    RANGE_EFFICIENCY_WINDOW,
    RSI_REGIME_BEARISH,
    RSI_REGIME_BULLISH,
    RSI_STATE_OVERBOUGHT,
    RSI_STATE_OVERSOLD,
    VOL_PERCENTILE_WINDOW,
)


__all__ = ["build_derived_indicators"]


COL_MA_20 = ma_col(20)
COL_MA_50 = ma_col(50)
COL_MA_200 = ma_col(200)

COL_ATR_14 = atr_col(14)
COL_ROLLING_STD_20 = rolling_std_col(20)

COL_HIGHEST_HIGH_20 = highest_high_col(20)
COL_LOWEST_LOW_20 = lowest_low_col(20)

COL_RETURN_1D = return_col(1)
COL_AVG_VOLUME_20 = avg_volume_col(20)

REQUIRED_L2_BASE_COLUMNS = {
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
    COL_MA_20,
    COL_MA_50,
    COL_MA_200,
    COL_RSI_14,
    COL_MACD_DIFF,
    COL_MACD_DEA,
    COL_MACD_HIST,
    COL_ATR_14,
    COL_ROLLING_STD_20,
    COL_BOLL_MID,
    COL_BOLL_UPPER,
    COL_BOLL_LOWER,
    COL_BOLL_WIDTH,
    COL_HIGHEST_HIGH_20,
    COL_LOWEST_LOW_20,
    COL_AVG_VOLUME_20,
    COL_RETURN_1D,
}


def build_derived_feature_series(df: pd.DataFrame) -> pd.DataFrame:
    out = _validate_input(df)

    out = _add_price_vs_ma_indicators(out)
    out = _add_ma_slope_indicators(out)
    out = _add_ma_alignment_indicators(out)
    out = _add_trend_strength_indicator(out)

    out = _add_rsi_state_indicators(out)
    out = _add_macd_state_indicators(out)

    out = _add_atr_pct_indicator(out)
    out = _add_volatility_percentile_indicators(out)
    out = _add_bollinger_position_indicators(out)

    out = _add_distance_to_recent_levels(out)
    out = _add_range_efficiency_indicator(out)
    out = _add_chopiness_index(out)
    out = _add_drawdown_rebound_indicators(out)

    out = _add_volume_structure_indicators(out)
    out = _add_symbol_vs_market_indicators(out)
    out = _add_sector_strength_indicator(out)

    return out


def _validate_input(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_L2_BASE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required L2 base columns: {sorted(missing)}")

    out = df.copy()
    out[COL_DATE] = pd.to_datetime(out[COL_DATE])
    out = out.sort_values(COL_DATE).reset_index(drop=True)
    return out


def _add_price_vs_ma_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_PRICE_VS_MA20] = out[COL_CLOSE] / out[COL_MA_20] - 1.0
    out[COL_PRICE_VS_MA50] = out[COL_CLOSE] / out[COL_MA_50] - 1.0
    out[COL_PRICE_VS_MA200] = out[COL_CLOSE] / out[COL_MA_200] - 1.0
    return out


def _slope(series: pd.Series, window: int) -> pd.Series:
    return (series - series.shift(window)) / window


def _add_ma_slope_indicators(
    df: pd.DataFrame,
    window: int = MA_SLOPE_WINDOW,
) -> pd.DataFrame:
    out = df.copy()
    out[COL_MA20_SLOPE] = _slope(out[COL_MA_20], window=window)
    out[COL_MA50_SLOPE] = _slope(out[COL_MA_50], window=window)
    out[COL_MA200_SLOPE] = _slope(out[COL_MA_200], window=window)
    return out


def _add_ma_alignment_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_MA_ALIGNMENT_BULLISH] = (
        (out[COL_MA_20] > out[COL_MA_50]) & (out[COL_MA_50] > out[COL_MA_200])
    )
    out[COL_MA_ALIGNMENT_BEARISH] = (
        (out[COL_MA_20] < out[COL_MA_50]) & (out[COL_MA_50] < out[COL_MA_200])
    )
    return out


def _add_trend_strength_indicator(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_TREND_STRENGTH] = (
        out[COL_PRICE_VS_MA20].abs()
        + out[COL_PRICE_VS_MA50].abs()
        + out[COL_MA20_SLOPE].abs().fillna(0.0)
    )
    return out


def _map_rsi_state(x: float) -> Optional[str]:
    if pd.isna(x):
        return None
    if x >= RSI_STATE_OVERBOUGHT:
        return STATE_OVERBOUGHT
    if x <= RSI_STATE_OVERSOLD:
        return STATE_OVERSOLD
    return STATE_NEUTRAL


def _map_rsi_regime(x: float) -> Optional[str]:
    if pd.isna(x):
        return None
    if x >= RSI_REGIME_BULLISH:
        return STATE_BULLISH
    if x <= RSI_REGIME_BEARISH:
        return STATE_BEARISH
    return STATE_NEUTRAL


def _add_rsi_state_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_RSI_STATE] = out[COL_RSI_14].apply(_map_rsi_state)
    out[COL_RSI_REGIME] = out[COL_RSI_14].apply(_map_rsi_regime)
    return out


def _add_macd_state_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    diff = out[COL_MACD_DIFF]
    dea = out[COL_MACD_DEA]
    hist = out[COL_MACD_HIST]

    cross_up = (diff > dea) & (diff.shift(1) <= dea.shift(1))
    cross_down = (diff < dea) & (diff.shift(1) >= dea.shift(1))

    out[COL_MACD_CROSS_STATE] = np.select(
        [cross_up, cross_down],
        [STATE_GOLDEN_CROSS, STATE_DEATH_CROSS],
        default=STATE_NONE,
    )

    out[COL_MACD_TREND_STATE] = np.select(
        [hist > 0, hist < 0],
        [STATE_BULLISH, STATE_BEARISH],
        default=STATE_NEUTRAL,
    )
    return out


def _add_atr_pct_indicator(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_ATR_PCT] = out[COL_ATR_14] / out[COL_CLOSE]
    return out


def _rolling_percentile_last(series: pd.Series) -> float:
    s = pd.Series(series)
    return s.rank(pct=True).iloc[-1]


def _add_volatility_percentile_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out[COL_VOL_PERCENTILE_20] = (
        out[COL_ROLLING_STD_20]
        .rolling(VOL_PERCENTILE_WINDOW, min_periods=VOL_PERCENTILE_WINDOW)
        .apply(_rolling_percentile_last, raw=False)
    )

    out[COL_ATR_PERCENTILE_60] = (
        out[COL_ATR_PCT]
        .rolling(ATR_PERCENTILE_WINDOW, min_periods=ATR_PERCENTILE_WINDOW)
        .apply(_rolling_percentile_last, raw=False)
    )

    return out


def _add_bollinger_position_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    band_range = (out[COL_BOLL_UPPER] - out[COL_BOLL_LOWER]).replace(0, np.nan)

    out[COL_BOLL_POSITION] = (out[COL_CLOSE] - out[COL_BOLL_LOWER]) / band_range
    out[COL_PRICE_VS_BOLL_MID] = out[COL_CLOSE] / out[COL_BOLL_MID] - 1.0
    out[COL_BOLL_WIDTH_PCT] = out[COL_BOLL_WIDTH] / out[COL_BOLL_MID]
    return out


def _add_distance_to_recent_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_DISTANCE_TO_RECENT_HIGH] = out[COL_CLOSE] / out[COL_HIGHEST_HIGH_20] - 1.0
    out[COL_DISTANCE_TO_RECENT_LOW] = out[COL_CLOSE] / out[COL_LOWEST_LOW_20] - 1.0
    return out


def _add_range_efficiency_indicator(
    df: pd.DataFrame,
    window: int = RANGE_EFFICIENCY_WINDOW,
) -> pd.DataFrame:
    out = df.copy()

    absolute_move = (out[COL_CLOSE] - out[COL_CLOSE].shift(window)).abs()
    path_length = out[COL_CLOSE].diff().abs().rolling(window, min_periods=window).sum()

    out[COL_RANGE_EFFICIENCY] = absolute_move / path_length.replace(0, np.nan)
    return out


def _add_chopiness_index(
    df: pd.DataFrame,
    window: int = CHOPINESS_WINDOW,
) -> pd.DataFrame:
    out = df.copy()

    tr = pd.concat(
        [
            out[COL_HIGH] - out[COL_LOW],
            (out[COL_HIGH] - out[COL_CLOSE].shift(1)).abs(),
            (out[COL_LOW] - out[COL_CLOSE].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    tr_sum = tr.rolling(window, min_periods=window).sum()
    hh = out[COL_HIGH].rolling(window, min_periods=window).max()
    ll = out[COL_LOW].rolling(window, min_periods=window).min()

    denominator = (hh - ll).replace(0, np.nan)
    out[COL_CHOPINESS_INDEX] = 100 * np.log10(tr_sum / denominator) / np.log10(window)
    return out


def _add_drawdown_rebound_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rolling_peak = out[COL_CLOSE].cummax()
    rolling_low = out[COL_CLOSE].cummin()

    out[COL_DRAWDOWN_FROM_PEAK] = out[COL_CLOSE] / rolling_peak - 1.0
    out[COL_REBOUND_FROM_LOW] = out[COL_CLOSE] / rolling_low - 1.0
    return out


def _add_volume_structure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[COL_VOLUME_VS_AVG20] = out[COL_VOLUME] / out[COL_AVG_VOLUME_20]

    avg_avg_volume_20 = out[COL_AVG_VOLUME_20].rolling(
        LIQUIDITY_SCORE_STABILITY_WINDOW,
        min_periods=LIQUIDITY_SCORE_STABILITY_WINDOW,
    ).mean()

    out[COL_LIQUIDITY_SCORE] = (
        LIQUIDITY_SCORE_WEIGHT_REL_VOL * out[COL_VOLUME_VS_AVG20].clip(lower=0)
        + LIQUIDITY_SCORE_WEIGHT_STABILITY * (out[COL_AVG_VOLUME_20] / avg_avg_volume_20)
    )
    return out


def _add_symbol_vs_market_indicators(
    df: pd.DataFrame,
    market_return_col: str = COL_SPY_RETURN,
) -> pd.DataFrame:
    out = df.copy()
    if market_return_col in out.columns:
        out[COL_SYMBOL_VS_MARKET] = out[COL_RETURN_1D] - out[market_return_col]
    return out


def _add_sector_strength_indicator(
    df: pd.DataFrame,
    sector_return_col: str = COL_SECTOR_RETURN,
    market_return_col: str = COL_SPY_RETURN,
) -> pd.DataFrame:
    out = df.copy()
    if sector_return_col in out.columns and market_return_col in out.columns:
        out[COL_SECTOR_STRENGTH] = out[sector_return_col] - out[market_return_col]
    return out