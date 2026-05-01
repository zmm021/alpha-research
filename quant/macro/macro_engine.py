from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from quant.common.constants import StructureScores
from quant.common.enums import MacroState
from quant.common.math import RollingZScore
from quant.common.schemas import StructureOutput
from quant.macro.state import compute_macro_state_output


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

    # structure scores
    structure_scores: Dict[str, Any]

    # convenient aliases
    trend_strength: float
    risk_pressure: float

    # state
    macro_state: MacroState


class MacroEngine:
    """
    Incremental Macro Engine.

    Flow:
        indicators -> factors -> structure_scores -> state
    """

    def __init__(self, config: dict):
        self.config = config

        self.prev_spy_close: Optional[float] = None

        self.spy_return_z = RollingZScore(config["indicators"]["spy_z_window"])
        self.vix_z = RollingZScore(config["indicators"]["vix_z_window"])
        self.credit_z = RollingZScore(config["indicators"]["credit_z_window"])

        self.prev_state: Optional[MacroState] = None

    def warmup(self, spy_df, vix_df, credit_df):
        spy_close = spy_df["close"]
        vix_close = vix_df["close"]
        credit = credit_df["close"]

        self.prev_spy_close = float(spy_close.iloc[-1])

        spy_return_series = spy_close.pct_change().dropna()

        self.spy_return_z.warmup(spy_return_series)
        self.vix_z.warmup(vix_close)
        self.credit_z.warmup(credit)

        self.prev_state = MacroState.NEUTRAL

    def update(self, macro_bar: dict) -> MacroSnapshot:
        spy_close = float(macro_bar["spy"]["close"])
        vix_close = float(macro_bar["vix"]["close"])
        credit = float(macro_bar["credit"]["close"])

        # ===== indicators =====
        if self.prev_spy_close is None:
            spy_return = 0.0
        else:
            spy_return = (spy_close / self.prev_spy_close) - 1.0

        spy_return_z = self.spy_return_z.update(spy_return)
        vix_z = self.vix_z.update(vix_close)
        credit_z = self.credit_z.update(credit)

        self.prev_spy_close = spy_close

        # ===== factors =====
        trend_factor = spy_return_z * self.config["factors"]["trend_scale"]
        vol_factor = vix_z * self.config["factors"]["vol_scale"]
        credit_factor = credit_z * self.config["factors"]["credit_scale"]

        # ===== structure scores =====
        vol_risk = max(vol_factor, 0.0)
        credit_risk = max(credit_factor, 0.0)

        risk_pressure = (
            self.config["structure"]["vol_weight"] * vol_risk
            + self.config["structure"]["credit_weight"] * credit_risk
        )

        trend_strength = trend_factor

        structure_scores = {
            StructureScores.MACRO_TREND_STRENGTH: trend_strength,
            StructureScores.MACRO_RISK_PRESSURE: risk_pressure,
        }

        structure_output = StructureOutput(values=structure_scores)

        # ===== state =====
        state = compute_macro_state_output(
            structure_output=structure_output,
            config=self.config,
        )

        self.prev_state = state

        return MacroSnapshot(
            spy_return=spy_return,
            spy_return_z=spy_return_z,
            vix_z=vix_z,
            credit_z=credit_z,
            trend_factor=trend_factor,
            vol_factor=vol_factor,
            credit_factor=credit_factor,
            structure_scores=structure_scores,
            trend_strength=trend_strength,
            risk_pressure=risk_pressure,
            macro_state=state,
        )