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


def _compute_atr(df: pd.DataFrame, window: int) -> pd.Series:
    prev_close = df[Fields.CLOSE].shift(1)

    high_low = df[Fields.HIGH] - df[Fields.LOW]
    high_prev_close = (df[Fields.HIGH] - prev_close).abs()
    low_prev_close = (df[Fields.LOW] - prev_close).abs()

    true_range = pd.concat(
        [high_low, high_prev_close, low_prev_close],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(window=window, min_periods=window).mean()


def _compute_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (
        df[Fields.HIGH] + df[Fields.LOW] + df[Fields.CLOSE]
    ) / 3.0

    cum_pv = (typical_price * df[Fields.VOLUME]).cumsum()
    cum_vol = df[Fields.VOLUME].cumsum()

    return cum_pv / cum_vol.replace(0, pd.NA)


# =========================
# Core
# =========================

def compute_symbol_indicators(
    df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    """
    Compute phase-1 symbol indicators.

    Required input columns:
      - open
      - high
      - low
      - close
      - volume
    """
    _require_columns(
        df,
        [Fields.OPEN, Fields.HIGH, Fields.LOW, Fields.CLOSE, Fields.VOLUME],
        "symbol_df",
    )

    indicator_cfg = config["indicators"]

    ma_short_window = int(indicator_cfg["ma_short_window"])
    ma_long_window = int(indicator_cfg["ma_long_window"])
    atr_window = int(indicator_cfg["atr_window"])
    volume_window = int(indicator_cfg["volume_window"])
    high_window = int(indicator_cfg["high_window"])
    range_position_window = int(
        indicator_cfg.get("range_position_window", high_window)
    )

    out = pd.DataFrame(index=df.index)

    close = df[Fields.CLOSE]
    open_ = df[Fields.OPEN]
    high = df[Fields.HIGH]
    low = df[Fields.LOW]
    volume = df[Fields.VOLUME]

    # ===== Moving averages =====
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

    # ===== ATR =====
    atr = _compute_atr(df, atr_window)
    out[Indicators.ATR_PCT] = atr / close.replace(0, pd.NA)

    # ===== Position vs recent high =====
    rolling_high = high.rolling(
        window=high_window,
        min_periods=high_window,
    ).max()

    out[Indicators.DISTANCE_TO_HIGH] = (
        (rolling_high - close) / close.replace(0, pd.NA)
    )

    # ===== Range position =====
    range_low = low.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).min()

    range_high = high.rolling(
        window=range_position_window,
        min_periods=range_position_window,
    ).max()

    range_width = (range_high - range_low).replace(0, pd.NA)

    out[Indicators.RANGE_LOW] = range_low
    out[Indicators.RANGE_HIGH] = range_high
    out[Indicators.RANGE_POSITION] = (
        (close - range_low) / range_width
    ).clip(lower=0.0, upper=1.0)

    # ===== Volume =====
    avg_volume = volume.rolling(
        window=volume_window,
        min_periods=volume_window,
    ).mean()

    out[Indicators.VOLUME_RATIO] = volume / avg_volume.replace(0, pd.NA)

    # ===== Gap =====
    prev_close = close.shift(1)
    out[Indicators.GAP_PCT] = (
        (open_ - prev_close) / prev_close.replace(0, pd.NA)
    )

    # ===== VWAP =====
    vwap = _compute_vwap(df)
    out[Indicators.PRICE_VS_VWAP] = (
        (close - vwap) / vwap.replace(0, pd.NA)
    )

    return out


def compute_symbol_indicator_output(
    df: pd.DataFrame,
    config: ConfigDict,
) -> IndicatorOutput:
    indicator_df = compute_symbol_indicators(df, config)
    latest = indicator_df.iloc[-1].dropna().to_dict()
    return IndicatorOutput(values={k: float(v) for k, v in latest.items()})