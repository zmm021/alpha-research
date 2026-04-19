from __future__ import annotations

import pandas as pd

from quant.common.constants import Fields
from quant.common.schemas import IndicatorOutput
from quant.common.types import ConfigDict

from quant.symbol.indicator.common import require_symbol_ohlcv
from quant.symbol.indicator.intraday import compute_intraday_indicators
from quant.symbol.indicator.position import compute_position_indicators
from quant.symbol.indicator.trend import compute_trend_indicators
from quant.symbol.indicator.volatility import compute_volatility_indicators
from quant.symbol.indicator.volume import compute_volume_indicators


def compute_symbol_indicators(
    df: pd.DataFrame,
    config: ConfigDict,
) -> pd.DataFrame:
    """
    Compute symbol indicators from raw OHLCV bars.

    Required input columns:
      - open
      - high
      - low
      - close
      - volume
    """
    require_symbol_ohlcv(df, "symbol_df")

    indicator_cfg = config["indicators"]

    # 统一参数读取
    trend_cfg = {
        "ma_short_window": int(indicator_cfg["ma_short_window"]),
        "ma_long_window": int(indicator_cfg["ma_long_window"]),
    }

    volatility_cfg = {
        "atr_window": int(indicator_cfg["atr_window"]),
    }

    position_cfg = {
        "high_window": int(indicator_cfg["high_window"]),
        "range_position_window": int(
            indicator_cfg.get("range_position_window", indicator_cfg["high_window"])
        ),
    }

    volume_cfg = {
        "volume_window": int(indicator_cfg["volume_window"]),
    }

    intraday_cfg = {}

    out = pd.DataFrame(index=df.index)

    # ===== Trend =====
    trend_df = compute_trend_indicators(df, trend_cfg)

    # ===== Volatility =====
    volatility_df = compute_volatility_indicators(df, volatility_cfg)

    # ===== Position =====
    position_df = compute_position_indicators(df, position_cfg)

    # ===== Volume =====
    volume_df = compute_volume_indicators(df, volume_cfg)

    # ===== Intraday =====
    intraday_df = compute_intraday_indicators(df, intraday_cfg)

    out = (
        out.join(trend_df)
        .join(volatility_df)
        .join(position_df)
        .join(volume_df)
        .join(intraday_df)
    )

    return out


def compute_symbol_indicator_output(
    df: pd.DataFrame,
    config: ConfigDict,
) -> IndicatorOutput:
    indicator_df = compute_symbol_indicators(df, config)
    latest = indicator_df.iloc[-1].dropna().to_dict()
    return IndicatorOutput(values={k: float(v) for k, v in latest.items()})