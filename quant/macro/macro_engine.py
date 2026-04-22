from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from collections import deque
import numpy as np
from quant.common.enums import MacroState
from quant.common.math import RollingZScore


# =========================================================
# Snapshot
# =========================================================

@dataclass
class MacroSnapshot:
    # indicators
    spy_return: float
    spy_return_z: float
    vix_z: float
    credit_z: float

    # factors
    trend_factor: float
    vol_factor: float
    credit_factor: float

    # context
    risk_context: float

    # state
    macro_state: str


# =========================================================
# Engine
# =========================================================

class MacroEngine:
    """
    Incremental Macro Engine

    - warmup: initialize rolling states
    - update: consume one bar_bundle and output MacroSnapshot
    """

    def __init__(self, config: dict):
        self.config = config

        # prev values
        self.prev_spy_close: Optional[float] = None

        # rolling states
        self.spy_return_z = RollingZScore(config["indicators"]["spy_z_window"])
        self.vix_z = RollingZScore(config["indicators"]["vix_z_window"])
        self.credit_z = RollingZScore(config["indicators"]["credit_z_window"])

        # prev state
        self.prev_state: Optional[str] = None

    # =====================================================
    # Warmup
    # =====================================================

    def warmup(self, spy_df, vix_df, credit_df):

        spy_close = spy_df["close"]
        vix_close = vix_df["close"]
        credit = credit_df["close"]

        # prev close
        self.prev_spy_close = float(spy_close.iloc[-1])

        # compute spy return series
        spy_return_series = spy_close.pct_change().dropna()

        # warmup rolling
        self.spy_return_z.warmup(spy_return_series)
        self.vix_z.warmup(vix_close)
        self.credit_z.warmup(credit)

        # initial state
        self.prev_state = "neutral"

    # =====================================================
    # Update
    # =====================================================

    def update(self, macro_bar: dict) -> MacroSnapshot:
        """
        macro_bar format:

        {
            "spy": {"close": ...},
            "vix": {"close": ...},
            "credit": {"close": ...}
        }
        """

        spy_close = float(macro_bar["spy"]["close"])
        vix_close = float(macro_bar["vix"]["close"])
        credit = float(macro_bar["credit"]["close"])

        # -------------------------
        # indicators
        # -------------------------

        if self.prev_spy_close is None:
            spy_return = 0.0
        else:
            spy_return = (spy_close / self.prev_spy_close) - 1.0

        spy_return_z = self.spy_return_z.update(spy_return)
        vix_z = self.vix_z.update(vix_close)
        credit_z = self.credit_z.update(credit)

        self.prev_spy_close = spy_close

        # -------------------------
        # factors
        # -------------------------

        trend_factor = spy_return_z * self.config["factors"]["trend_scale"]
        vol_factor = vix_z * self.config["factors"]["vol_scale"]
        credit_factor = credit_z * self.config["factors"]["credit_scale"]


        # -------------------------
        # context
        # -------------------------

        vol_risk = max(vol_factor, 0.0)
        credit_risk = max(credit_factor, 0.0)

        risk_context = (
            self.config["contexts"]["vol_weight"] * vol_risk
            + self.config["contexts"]["credit_weight"] * credit_risk
        )
 
        # -------------------------
        # state
        # -------------------------

        if risk_context >= self.config["state"]["risk_off_threshold"]:
            state = MacroState.RISK_OFF
        elif (
            trend_factor >= self.config["state"]["risk_on_trend_threshold"]
            and risk_context <= self.config["state"]["risk_on_max_risk"]
        ):
            state = MacroState.RISK_ON
        else:
            state = MacroState.NEUTRAL

        self.prev_state = state

        # -------------------------
        # snapshot
        # -------------------------

        return MacroSnapshot(
            spy_return=spy_return,
            spy_return_z=spy_return_z,
            vix_z=vix_z,
            credit_z=credit_z,
            trend_factor=trend_factor,
            vol_factor=vol_factor,
            credit_factor=credit_factor,
            risk_context=risk_context,
            macro_state=state,
        )