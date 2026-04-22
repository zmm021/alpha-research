from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict

from quant.common.math import (
    RollingMean,
    RollingStd,
    RollingMax,
    RollingMin,
    RollingSlope,
    RollingSum,
    EMA,
    RollingATR,
)


@dataclass
class SymbolIndicatorState:
    """
    Stateful container for symbol-level incremental indicator calculations.

    Design goals:
    1. Preserve previously available indicator capabilities
    2. Add batch-compatible indicator column names required by symbol factor pipeline
    3. Ensure warmup + update do not double-feed the same bar
    """

    # -------------------------
    # Trend
    # -------------------------
    ma_short: RollingMean
    ma_long: RollingMean
    ma_long_slope: RollingSlope

    # optional EMA trend helpers
    ema_short: EMA
    ema_long: EMA

    # -------------------------
    # Volatility
    # -------------------------
    atr: RollingATR
    return_std: RollingStd

    # -------------------------
    # Volume / Liquidity
    # -------------------------
    volume_ma: RollingMean
    volume_sum: RollingSum

    # -------------------------
    # Position / Range
    # -------------------------
    rolling_high: RollingMax
    rolling_low: RollingMin

    # -------------------------
    # VWAP cumulative state
    # -------------------------
    cum_pv: float = 0.0
    cum_vol: float = 0.0

    # -------------------------
    # Previous raw values
    # -------------------------
    prev_close: Optional[float] = None
    prev_open: Optional[float] = None
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    prev_volume: Optional[float] = None

    # previous derived values
    prev_ma_short: Optional[float] = None
    prev_ma_long: Optional[float] = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "SymbolIndicatorState":
        indicators_cfg = config.get("indicators", {})

        ma_short_window = int(indicators_cfg["ma_short_window"])
        ma_long_window = int(indicators_cfg["ma_long_window"])
        atr_window = int(indicators_cfg["atr_window"])
        volume_window = int(indicators_cfg["volume_window"])
        high_window = int(indicators_cfg["high_window"])
        range_position_window = int(indicators_cfg["range_position_window"])

        return cls(
            # trend
            ma_short=RollingMean(ma_short_window),
            ma_long=RollingMean(ma_long_window),
            ma_long_slope=RollingSlope(ma_long_window),
            ema_short=EMA(ma_short_window),
            ema_long=EMA(ma_long_window),

            # volatility
            atr=RollingATR(atr_window),
            return_std=RollingStd(atr_window),

            # volume / liquidity
            volume_ma=RollingMean(volume_window),
            volume_sum=RollingSum(volume_window),

            # position / range
            rolling_high=RollingMax(high_window),
            rolling_low=RollingMin(range_position_window),
        )

    def warmup(self, symbol_df) -> None:
        """
        Warm up all rolling states from historical symbol dataframe.

        Expected columns:
        - open
        - high
        - low
        - close
        - volume

        Important:
        warmup should fully initialize state.
        It must NOT push the last bar again after initialization.
        """

        if symbol_df is None or symbol_df.empty:
            return

        for _, row in symbol_df.iterrows():
            self.update(
                {
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                }
            )

    def update(self, bar: Dict[str, Any]) -> Dict[str, float]:
        """
        Update all indicator states with one new symbol bar.

        Expected bar keys:
        - open
        - high
        - low
        - close
        - volume

        Returns a dict that preserves previous incremental outputs while also
        exposing batch-compatible indicator column names required by factor pipeline.
        """

        open_ = self._safe_float(bar.get("open"), 0.0)
        high = self._safe_float(bar.get("high"), 0.0)
        low = self._safe_float(bar.get("low"), 0.0)
        close = self._safe_float(bar.get("close"), 0.0)
        volume = self._safe_float(bar.get("volume"), 0.0)

        # -------- returns / gaps --------
        if self.prev_close is None or self.prev_close == 0:
            return_1d = 0.0
            gap_return = 0.0
            gap_pct = 0.0
        else:
            return_1d = (close / self.prev_close) - 1.0
            gap_return = (open_ / self.prev_close) - 1.0
            gap_pct = (open_ - self.prev_close) / self.prev_close

        intraday_return = (close / open_) - 1.0 if open_ != 0 else 0.0

        # -------- trend --------
        ma_short = self.ma_short.update(close)
        ma_long = self.ma_long.update(close)

        # keep old slope helper
        ma_long_slope = self.ma_long_slope.update(close)

        # batch-compatible slopes are based on MA deltas
        ma_short_slope = 0.0 if self.prev_ma_short is None else (ma_short - self.prev_ma_short)
        ma_long_slope_raw = 0.0 if self.prev_ma_long is None else (ma_long - self.prev_ma_long)

        ema_short = self.ema_short.update(close)
        ema_long = self.ema_long.update(close)

        ma_cross = ma_short - ma_long

        # -------- volatility --------
        atr = self.atr.update(high=high, low=low, close=close)
        atr_pct = atr / close if close != 0 else 0.0

        return_std = self.return_std.update(return_1d)

        # -------- volume / liquidity --------
        volume_ma = self.volume_ma.update(volume)
        volume_sum = self.volume_sum.update(volume)
        volume_ratio = (volume / volume_ma) if volume_ma not in (0, None) else 0.0

        # -------- position / range --------
        rolling_high = self.rolling_high.update(high)
        rolling_low = self.rolling_low.update(low)

        range_width = rolling_high - rolling_low
        if range_width == 0:
            range_position = 0.5
        else:
            range_position = (close - rolling_low) / range_width

        distance_to_high = (rolling_high - close) / close if close != 0 else 0.0

        # -------- VWAP --------
        typical_price = (high + low + close) / 3.0
        self.cum_pv += typical_price * volume
        self.cum_vol += volume

        vwap = self.cum_pv / self.cum_vol if self.cum_vol != 0 else 0.0
        price_vs_vwap = (close - vwap) / vwap if vwap != 0 else 0.0

        # -------- save prev --------
        self.prev_open = open_
        self.prev_high = high
        self.prev_low = low
        self.prev_close = close
        self.prev_volume = volume

        self.prev_ma_short = ma_short
        self.prev_ma_long = ma_long

        # Return a superset:
        # 1. old incremental fields
        # 2. batch-compatible fields needed by factor pipeline
        return {
            # ==========================================
            # raw-ish
            # ==========================================
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,

            # ==========================================
            # return / intraday
            # ==========================================
            "return_1d": return_1d,
            "gap_return": gap_return,
            "gap_pct": gap_pct,
            "intraday_return": intraday_return,

            # ==========================================
            # trend (original names kept)
            # ==========================================
            "ma_short": ma_short,
            "ma_long": ma_long,
            "ma_long_slope": ma_long_slope,
            "ema_short": ema_short,
            "ema_long": ema_long,
            "ma_cross": ma_cross,

            # ==========================================
            # batch-compatible trend names
            # ==========================================
            "ma20": ma_short,
            "ma50": ma_long,
            "ma20_slope": ma_short_slope,
            "ma50_slope": ma_long_slope_raw,

            # ==========================================
            # volatility
            # ==========================================
            "atr": atr,
            "atr_pct": atr_pct,
            "return_std": return_std,

            # ==========================================
            # volume / liquidity
            # ==========================================
            "volume_ma": volume_ma,
            "volume_sum": volume_sum,
            "volume_ratio": volume_ratio,

            # ==========================================
            # position / range
            # ==========================================
            "rolling_high": rolling_high,
            "rolling_low": rolling_low,
            "range_high": rolling_high,
            "range_low": rolling_low,
            "range_position": range_position,
            "distance_to_high": distance_to_high,

            # ==========================================
            # vwap
            # ==========================================
            "vwap": vwap,
            "price_vs_vwap": price_vs_vwap,
        }

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default