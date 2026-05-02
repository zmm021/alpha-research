from __future__ import annotations

from typing import Any

from quant.macro.macro_engine import MacroEngine
from quant.sector.sector_engine import SectorEngine
from quant.symbol.symbol_engine import SymbolEngine

from quant.context.s1_structure_context import S1StructureContext
from quant.common.constants import StructureScores


class S1StructureEngine:
    """
    S1 Structure Engine

    负责：
        - 调用 macro / sector / symbol engine
        - 聚合 snapshot
        - 构建 S1StructureContext
    """

    def __init__(self, config: dict):
        self.macro_engine = MacroEngine(config["macro"])
        self.sector_engine = SectorEngine(config["sector"])
        self.symbol_engine = SymbolEngine(config["symbol"])

    # ==========================================
    # Warmup
    # ==========================================
    def warmup(
        self,
        macro_data: dict,
        sector_data: dict,
        symbol_data: dict,
    ):
        self.macro_engine.warmup(**macro_data)
        self.sector_engine.warmup(**sector_data)
        self.symbol_engine.warmup(symbol_data)

    # ==========================================
    # Update
    # ==========================================
    def update(
        self,
        macro_bar: dict,
        sector_bar: dict,
        symbol_bar: dict,
    ) -> S1StructureContext:

        macro_snap = self.macro_engine.update(macro_bar)
        sector_snap = self.sector_engine.update(sector_bar)
        symbol_snap = self.symbol_engine.update(symbol_bar)

        return self._build_context(
            macro_snap,
            sector_snap,
            symbol_snap,
        )

    # ==========================================
    # Build S1 Context
    # ==========================================
    def _build_context(
        self,
        macro_snap,
        sector_snap,
        symbol_snap,
    ) -> S1StructureContext:

        symbol_scores = symbol_snap.structure_scores
        sector_scores = sector_snap.structure_scores
        macro_scores = macro_snap.structure_scores

        return S1StructureContext(
            # ===== states =====
            macro_state=macro_snap.macro_state,
            sector_state=sector_snap.sector_state,
            symbol_state=symbol_snap.symbol_state,

            # ===== scores =====
            macro_scores=macro_scores,
            sector_scores=sector_scores,
            symbol_scores=symbol_scores,

            # ===== multi-scale =====
            range_position_short=symbol_scores.get(
                StructureScores.SYMBOL_RANGE_POSITION_SHORT
            ),
            range_position_mid=symbol_scores.get(
                StructureScores.SYMBOL_RANGE_POSITION_MID
            ),

            trend_slope_short=symbol_scores.get(
                StructureScores.SYMBOL_TREND_SLOPE
            ),
            trend_slope_mid=symbol_scores.get(
                StructureScores.SYMBOL_TREND_SLOPE
            ),

            trend_strength=symbol_scores.get(
                StructureScores.SYMBOL_TREND_STRENGTH
            ),

            liquidity_quality=symbol_scores.get(
                StructureScores.SYMBOL_LIQUIDITY_QUALITY
            ),

            reversal_pressure=symbol_scores.get(
                StructureScores.SYMBOL_REVERSAL_PRESSURE
            ),

            volatility_state=symbol_scores.get(
                StructureScores.SYMBOL_VOLATILITY_STATE
            ),

            # ===== macro / sector shortcuts =====
            macro_risk_pressure=macro_scores.get(
                StructureScores.MACRO_RISK_PRESSURE
            ),

            sector_support_score=sector_scores.get(
                StructureScores.SECTOR_SUPPORT_SCORE
            ),

            sector_breadth_health=sector_scores.get(
                StructureScores.SECTOR_BREADTH_HEALTH
            ),

            # ===== snapshots =====
            macro_snapshot=macro_snap,
            sector_snapshot=sector_snap,
            symbol_snapshot=symbol_snap,
        )