from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict

from quant.common.math import (
    RollingMean,
    RollingStd,
    RollingSlope,
    RollingSum,
    EMA,
    RollingATR,
)


@dataclass
class SymbolIndicatorState:
    ma_short: RollingMean
    ma_long: RollingMean
    ma_long_slope: RollingSlope

    ema_short: EMA
    ema_long: EMA

    atr: RollingATR
    return_std: RollingStd

    volume_ma: RollingMean
    volume_sum: RollingSum

    high_window_short: int
    range_position_window_short: int
    high_window_mid: int
    range_position_window_mid: int

    cum_pv: float = 0.0
    cum_vol: float = 0.0

    prev_close: Optional[float] = None
    prev_open: Optional[float] = None
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    prev_volume: Optional[float] = None

    prev_ma_short: Optional[float] = None
    prev_ma_long: Optional[float] = None
    prev_volume_ma: Optional[float] = None

    _high_short_buffer: list[float] | None = None
    _range_high_short_buffer: list[float] | None = None
    _range_low_short_buffer: list[float] | None = None

    _high_mid_buffer: list[float] | None = None
    _range_high_mid_buffer: list[float] | None = None
    _range_low_mid_buffer: list[float] | None = None

    _volume_buffer: list[float] | None = None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "SymbolIndicatorState":
        indicators_cfg = config.get("indicators", {})

        ma_short_window = int(indicators_cfg["ma_short_window"])
        ma_long_window = int(indicators_cfg["ma_long_window"])
        atr_window = int(indicators_cfg["atr_window"])
        volume_window = int(indicators_cfg["volume_window"])

        return cls(
            ma_short=RollingMean(ma_short_window),
            ma_long=RollingMean(ma_long_window),
            ma_long_slope=RollingSlope(ma_long_window),
            ema_short=EMA(ma_short_window),
            ema_long=EMA(ma_long_window),

            atr=RollingATR(atr_window),
            return_std=RollingStd(atr_window),

            volume_ma=RollingMean(volume_window),
            volume_sum=RollingSum(volume_window),

            high_window_short=int(indicators_cfg["high_window_short"]),
            range_position_window_short=int(indicators_cfg["range_position_window_short"]),
            high_window_mid=int(indicators_cfg["high_window_mid"]),
            range_position_window_mid=int(indicators_cfg["range_position_window_mid"]),
        )

    def warmup(self, symbol_df) -> None:
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
        open_ = self._safe_float(bar.get("open"), 0.0)
        high = self._safe_float(bar.get("high"), 0.0)
        low = self._safe_float(bar.get("low"), 0.0)
        close = self._safe_float(bar.get("close"), 0.0)
        volume = self._safe_float(bar.get("volume"), 0.0)

        self._init_buffers()

        # -------- returns / gaps --------
        if self.prev_close is None or self.prev_close == 0:
            return_1d = 0.0
            gap_return = 0.0
            gap_pct = 0.0
        else:
            return_1d = (close / self.prev_close) - 1.0
            gap_return = (open_ / self.prev_close) - 1.0
            gap_pct = gap_return

        intraday_return = (close / open_) - 1.0 if open_ != 0 else 0.0

        # -------- trend --------
        ma_short = self.ma_short.update(close)
        ma_long = self.ma_long.update(close)

        ma_long_slope = self.ma_long_slope.update(close)

        ma_short_slope = (
            0.0 if self.prev_ma_short is None else ma_short - self.prev_ma_short
        )
        ma_long_slope_raw = (
            0.0 if self.prev_ma_long is None else ma_long - self.prev_ma_long
        )

        ema_short = self.ema_short.update(close)
        ema_long = self.ema_long.update(close)
        ma_cross = ma_short - ma_long

        # -------- volatility --------
        atr = self.atr.update(high=high, low=low, close=close)
        atr_pct = atr / close if close != 0 else None
        return_std = self.return_std.update(return_1d)

        # -------- volume / liquidity --------
        self._volume_buffer.append(volume)
        if len(self._volume_buffer) > self.volume_ma.window:
            self._volume_buffer.pop(0)

        volume_ready = len(self._volume_buffer) == self.volume_ma.window
        volume_ma = (
            sum(self._volume_buffer) / len(self._volume_buffer)
            if volume_ready
            else None
        )
        volume_sum = sum(self._volume_buffer)

        volume_ratio = (
            volume / volume_ma
            if volume_ready and volume_ma not in (0, None)
            else None
        )

        # -------- position / range short --------
        (
            range_high_short,
            range_low_short,
            range_position_short,
            distance_to_high_short,
        ) = self._update_range(
            high=high,
            low=low,
            close=close,
            high_buffer=self._high_short_buffer,
            range_high_buffer=self._range_high_short_buffer,
            range_low_buffer=self._range_low_short_buffer,
            high_window=self.high_window_short,
            range_position_window=self.range_position_window_short,
        )

        # -------- position / range mid --------
        (
            range_high_mid,
            range_low_mid,
            range_position_mid,
            distance_to_high_mid,
        ) = self._update_range(
            high=high,
            low=low,
            close=close,
            high_buffer=self._high_mid_buffer,
            range_high_buffer=self._range_high_mid_buffer,
            range_low_buffer=self._range_low_mid_buffer,
            high_window=self.high_window_mid,
            range_position_window=self.range_position_window_mid,
        )

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
        self.prev_volume_ma = volume_ma

        return {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,

            "return_1d": return_1d,
            "gap_return": gap_return,
            "gap_pct": gap_pct,
            "intraday_return": intraday_return,

            "ma_short": ma_short,
            "ma_long": ma_long,
            "ma_long_slope": ma_long_slope,
            "ema_short": ema_short,
            "ema_long": ema_long,
            "ma_cross": ma_cross,

            "ma20": ma_short,
            "ma50": ma_long,
            "ma20_slope": ma_short_slope,
            "ma50_slope": ma_long_slope_raw,

            "atr": atr,
            "atr_pct": atr_pct,
            "return_std": return_std,

            "volume_ma": volume_ma,
            "volume_sum": volume_sum,
            "volume_ratio": volume_ratio,

            "range_high_short": range_high_short,
            "range_low_short": range_low_short,
            "range_position_short": range_position_short,
            "distance_to_high_short": distance_to_high_short,

            "range_high_mid": range_high_mid,
            "range_low_mid": range_low_mid,
            "range_position_mid": range_position_mid,
            "distance_to_high_mid": distance_to_high_mid,

            "vwap": vwap,
            "price_vs_vwap": price_vs_vwap,
        }

    def _init_buffers(self) -> None:
        if self._high_short_buffer is None:
            self._high_short_buffer = []
        if self._range_high_short_buffer is None:
            self._range_high_short_buffer = []
        if self._range_low_short_buffer is None:
            self._range_low_short_buffer = []

        if self._high_mid_buffer is None:
            self._high_mid_buffer = []
        if self._range_high_mid_buffer is None:
            self._range_high_mid_buffer = []
        if self._range_low_mid_buffer is None:
            self._range_low_mid_buffer = []

        if self._volume_buffer is None:
            self._volume_buffer = []

    @staticmethod
    def _update_range(
        *,
        high: float,
        low: float,
        close: float,
        high_buffer: list[float],
        range_high_buffer: list[float],
        range_low_buffer: list[float],
        high_window: int,
        range_position_window: int,
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        # distance_to_high uses high_window
        high_buffer.append(high)
        if len(high_buffer) > high_window:
            high_buffer.pop(0)

        high_ready = len(high_buffer) == high_window
        rolling_high = max(high_buffer) if high_ready else None

        distance_to_high = (
            (rolling_high - close) / close
            if high_ready and close != 0 and rolling_high is not None
            else None
        )

        # range high / low / position use range_position_window
        range_high_buffer.append(high)
        if len(range_high_buffer) > range_position_window:
            range_high_buffer.pop(0)

        range_low_buffer.append(low)
        if len(range_low_buffer) > range_position_window:
            range_low_buffer.pop(0)

        range_high_ready = len(range_high_buffer) == range_position_window
        range_low_ready = len(range_low_buffer) == range_position_window
        range_ready = range_high_ready and range_low_ready

        range_high = max(range_high_buffer) if range_high_ready else None
        range_low = min(range_low_buffer) if range_low_ready else None

        if not range_ready or range_high is None or range_low is None:
            range_position = None
        else:
            range_width = range_high - range_low
            if range_width == 0:
                range_position = None
            else:
                range_position = min(
                    max((close - range_low) / range_width, 0.0),
                    1.0,
                )

        return range_high, range_low, range_position, distance_to_high

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default