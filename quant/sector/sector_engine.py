from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import pandas as pd

from quant.common.enums import SectorState
from quant.common.math import RollingMean, RollingZScore


@dataclass
class SectorSnapshot:
    # indicators
    rs_z: float
    rs_momentum: float
    breadth: float
    breadth_momentum: float
    vol_z: float
    vol_trend: float

    # factors
    rs_factor: float
    breadth_factor: float
    participation_factor: float
    momentum_factor: float

    # contexts
    context: float              # support_score
    breadth_health: float
    momentum: float

    # state
    state: SectorState


class SectorEngine:
    """
    Incremental sector engine aligned with batch pipeline:

    indicators:
      - rs_z_sector
      - rs_momentum_z_sector
      - breadth_frac_sector
      - breadth_momentum_sector
      - vol_ratio_z_sector
      - vol_trend_z_sector

    factors:
      - sector_relative_strength_factor_sector
      - sector_breadth_factor_sector
      - sector_participation_factor_sector
      - sector_momentun_factor_sector

    contexts:
      - sector_support_score_sector
      - sector_breadth_health_sector
      - sector_momentum_sector

    state:
      - sector_state_sector
    """

    def __init__(self, config: dict):
        self.config = config

        ind_cfg = config["indicators"]

        self.rs_window = int(ind_cfg["rs_window"])
        self.rs_z_window = int(ind_cfg["rs_z_window"])
        self.rs_momentum_window = int(ind_cfg["rs_momentum_window"])

        self.breadth_ma_window = int(ind_cfg["breadth_ma_window"])
        self.breadth_momentum_window = int(ind_cfg["breadth_momentum_window"])

        self.vol_window = int(ind_cfg["vol_window"])
        self.vol_z_window = int(ind_cfg["vol_z_window"])
        self.vol_trend_window = int(ind_cfg["vol_trend_window"])

        # rolling states
        self.sector_close_ma_for_return = RollingMean(self.rs_window)
        self.spy_close_ma_for_return = RollingMean(self.rs_window)

        self.rs_z_state = RollingZScore(self.rs_z_window)
        self.rs_diff_z_state = RollingZScore(self.rs_z_window)

        self.sector_volume_ma = RollingMean(self.vol_window)
        self.vol_ratio_z_state = RollingZScore(self.vol_z_window)
        self.vol_ratio_diff_z_state = RollingZScore(self.vol_z_window)

        # breadth members state: each member needs its own rolling MA
        self.member_ma_states: Dict[str, RollingMean] = {}

        # breadth aggregate series
        self.breadth_momentum_base = RollingMean(1)  # keep for compatibility
        self._breadth_history: list[float] = []

        # histories for N-step diff indicators
        self._rs_raw_history: list[float] = []
        self._vol_ratio_history: list[float] = []

        # previous raw values
        self.prev_sector_close: Optional[float] = None
        self.prev_spy_close: Optional[float] = None
        self.prev_rs_raw: Optional[float] = None
        self.prev_vol_ratio: Optional[float] = None

        # state
        self.prev_state: Optional[SectorState] = None

    # =====================================================
    # Warmup
    # =====================================================

    def warmup(
        self,
        sector_df: pd.DataFrame,
        spy_df: pd.DataFrame,
        members_df: pd.DataFrame,
    ) -> None:
        if sector_df is None or sector_df.empty:
            raise ValueError("sector_df is empty")
        if spy_df is None or spy_df.empty:
            raise ValueError("spy_df is empty")

        sector_close = sector_df["close"]
        sector_volume = sector_df["volume"]
        spy_close = spy_df["close"].reindex(sector_df.index)

        # -------------------------
        # warm up rs / vol chains
        # -------------------------
        for ts in sector_df.index:
            s_close = float(sector_close.loc[ts])
            s_vol = float(sector_volume.loc[ts])
            p_close = float(spy_close.loc[ts])

            # rolling means (kept for consistency / future compatibility)
            _ = self.sector_close_ma_for_return.update(s_close)
            _ = self.spy_close_ma_for_return.update(p_close)

            # volume ratio + N-step diff zscore
            vol_ratio_base = self.sector_volume_ma.update(s_vol)
            vol_ratio = (s_vol / vol_ratio_base) if vol_ratio_base not in (0, None) else 0.0
            _ = self.vol_ratio_z_state.update(vol_ratio)

            self._vol_ratio_history.append(vol_ratio)
            if len(self._vol_ratio_history) > self.vol_trend_window + 1:
                self._vol_ratio_history = self._vol_ratio_history[-(self.vol_trend_window + 1):]

            if len(self._vol_ratio_history) <= self.vol_trend_window:
                vol_ratio_diff = 0.0
            else:
                vol_ratio_diff = vol_ratio - self._vol_ratio_history[-(self.vol_trend_window + 1)]

            _ = self.vol_ratio_diff_z_state.update(vol_ratio_diff)

            # rs raw + N-step diff zscore
            if self.prev_sector_close is None or self.prev_spy_close is None:
                sector_ret = 0.0
                spy_ret_ = 0.0
            else:
                sector_ret = (
                    (s_close / self.prev_sector_close) - 1.0
                    if self.prev_sector_close != 0 else 0.0
                )
                spy_ret_ = (
                    (p_close / self.prev_spy_close) - 1.0
                    if self.prev_spy_close != 0 else 0.0
                )

            rs_raw = sector_ret - spy_ret_
            _ = self.rs_z_state.update(rs_raw)

            self._rs_raw_history.append(rs_raw)
            if len(self._rs_raw_history) > self.rs_momentum_window + 1:
                self._rs_raw_history = self._rs_raw_history[-(self.rs_momentum_window + 1):]

            if len(self._rs_raw_history) <= self.rs_momentum_window:
                rs_diff = 0.0
            else:
                rs_diff = rs_raw - self._rs_raw_history[-(self.rs_momentum_window + 1)]

            _ = self.rs_diff_z_state.update(rs_diff)

            self.prev_sector_close = s_close
            self.prev_spy_close = p_close
            self.prev_rs_raw = rs_raw
            self.prev_vol_ratio = vol_ratio

        # -------------------------
        # breadth warmup
        # -------------------------
        if members_df is None:
            members_df = pd.DataFrame(index=sector_df.index)

        members_df = members_df.reindex(sector_df.index)

        for symbol in members_df.columns:
            self.member_ma_states[symbol] = RollingMean(self.breadth_ma_window)

        for ts in sector_df.index:
            flags = []

            for symbol in members_df.columns:
                close_val = members_df.at[ts, symbol]
                if pd.isna(close_val):
                    continue

                close_val = float(close_val)
                ma_state = self.member_ma_states[symbol]
                member_ma = ma_state.update(close_val)

                # match batch behavior:
                # only emit usable flag once enough window is available
                ready = len(ma_state.buffer) >= self.breadth_ma_window
                if not ready:
                    continue

                flag = 1.0 if close_val > member_ma else 0.0
                flags.append(flag)

            breadth_frac = sum(flags) / len(flags) if flags else 0.0
            self._breadth_history.append(breadth_frac)

            if len(self._breadth_history) > self.breadth_momentum_window + 1:
                self._breadth_history = self._breadth_history[-(self.breadth_momentum_window + 1):]

        self.prev_state = SectorState.MIXED

    # =====================================================
    # Update
    # =====================================================

    def update(
        self,
        sector_bar: Dict[str, Any],
        spy_bar: Dict[str, Any],
        members_bar: Dict[str, Dict[str, float | None]],
    ) -> SectorSnapshot:
        fcfg = self.config["factors"]
        ccfg = self.config["contexts"]
        scfg = self.config["state"]

        sector_close = float(sector_bar["close"])
        sector_volume = float(sector_bar.get("volume", 0.0))
        spy_close = float(spy_bar["close"])

        # -------------------------
        # 1. RS indicators
        # -------------------------
        if self.prev_sector_close is None or self.prev_spy_close is None:
            sector_ret = 0.0
            spy_ret_ = 0.0
        else:
            sector_ret = (
                (sector_close / self.prev_sector_close) - 1.0
                if self.prev_sector_close != 0 else 0.0
            )
            spy_ret_ = (
                (spy_close / self.prev_spy_close) - 1.0
                if self.prev_spy_close != 0 else 0.0
            )

        rs_raw = sector_ret - spy_ret_
        rs_z = self.rs_z_state.update(rs_raw)

        self._rs_raw_history.append(rs_raw)
        if len(self._rs_raw_history) > self.rs_momentum_window + 1:
            self._rs_raw_history = self._rs_raw_history[-(self.rs_momentum_window + 1):]

        if len(self._rs_raw_history) <= self.rs_momentum_window:
            rs_diff = 0.0
        else:
            rs_diff = rs_raw - self._rs_raw_history[-(self.rs_momentum_window + 1)]

        rs_momentum = self.rs_diff_z_state.update(rs_diff)

        # -------------------------
        # 2. Breadth indicators
        # -------------------------
        flags = []

        for symbol, bar in members_bar.items():
            close_val = bar.get("close")
            if close_val is None:
                continue

            if symbol not in self.member_ma_states:
                self.member_ma_states[symbol] = RollingMean(self.breadth_ma_window)

            ma_state = self.member_ma_states[symbol]
            member_ma = ma_state.update(float(close_val))

            ready = len(ma_state.buffer) >= self.breadth_ma_window
            if not ready:
                continue

            flag = 1.0 if float(close_val) > member_ma else 0.0
            flags.append(flag)

        breadth = sum(flags) / len(flags) if flags else 0.0

        self._breadth_history.append(breadth)
        if len(self._breadth_history) > self.breadth_momentum_window + 1:
            self._breadth_history = self._breadth_history[-(self.breadth_momentum_window + 1):]

        if len(self._breadth_history) <= self.breadth_momentum_window:
            breadth_momentum = 0.0
        else:
            breadth_momentum = breadth - self._breadth_history[-(self.breadth_momentum_window + 1)]

        # -------------------------
        # 3. Volume / participation indicators
        # -------------------------
        vol_base = self.sector_volume_ma.update(sector_volume)
        vol_ratio = (sector_volume / vol_base) if vol_base not in (0, None) else 0.0
        vol_z = self.vol_ratio_z_state.update(vol_ratio)

        self._vol_ratio_history.append(vol_ratio)
        if len(self._vol_ratio_history) > self.vol_trend_window + 1:
            self._vol_ratio_history = self._vol_ratio_history[-(self.vol_trend_window + 1):]

        if len(self._vol_ratio_history) <= self.vol_trend_window:
            vol_ratio_diff = 0.0
        else:
            vol_ratio_diff = vol_ratio - self._vol_ratio_history[-(self.vol_trend_window + 1)]

        vol_trend = self.vol_ratio_diff_z_state.update(vol_ratio_diff)

        # -------------------------
        # 4. Factors (batch-equivalent)
        # -------------------------
        rs_factor = float(fcfg["rs_scale"]) * rs_z
        breadth_factor = float(fcfg["breadth_scale"]) * breadth
        participation_factor = float(fcfg["vol_scale"]) * vol_z

        momentum_factor = (
            float(fcfg["rs_momentum_scale"]) * rs_momentum
            + float(fcfg["breadth_momentum_scale"]) * breadth_momentum
            + float(fcfg["vol_trend_scale"]) * vol_trend
        )

        # -------------------------
        # 5. Contexts (batch-equivalent)
        # -------------------------
        context = (
            float(ccfg["rs_weight"]) * rs_factor
            + float(ccfg["breadth_weight"]) * breadth_factor
            + float(ccfg["vol_weight"]) * participation_factor
        )

        breadth_health = breadth_factor
        momentum = momentum_factor

        # -------------------------
        # 6. State (batch-equivalent)
        # -------------------------
        leading_threshold = float(scfg.get("leading_threshold", 0.5))
        weak_threshold = float(scfg.get("weak_threshold", -0.2))
        breadth_strong_threshold = float(scfg.get("breadth_strong_threshold", 0.55))
        breadth_weak_threshold = float(scfg.get("breadth_weak_threshold", 0.45))

        if context >= leading_threshold and breadth_health >= breadth_strong_threshold:
            state = SectorState.LEADING
        elif context <= weak_threshold or breadth_health <= breadth_weak_threshold:
            state = SectorState.WEAK
        else:
            state = SectorState.MIXED

        # -------------------------
        # save prev
        # -------------------------
        self.prev_sector_close = sector_close
        self.prev_spy_close = spy_close
        self.prev_rs_raw = rs_raw
        self.prev_vol_ratio = vol_ratio
        self.prev_state = state

        return SectorSnapshot(
            rs_z=rs_z,
            rs_momentum=rs_momentum,
            breadth=breadth,
            breadth_momentum=breadth_momentum,
            vol_z=vol_z,
            vol_trend=vol_trend,
            rs_factor=rs_factor,
            breadth_factor=breadth_factor,
            participation_factor=participation_factor,
            momentum_factor=momentum_factor,
            context=context,
            breadth_health=breadth_health,
            momentum=momentum,
            state=state,
        )