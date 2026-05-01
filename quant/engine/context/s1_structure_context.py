from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class S1StructureContext:
    """
    S1: 结构层

    来源：
        MacroEngine / SectorEngine / SymbolEngine

    承载：
        1. 各层 state
        2. 各层 structure scores
        3. 原始 snapshot，方便 debug
    """

    # ===== states =====
    macro_state: str = ""
    sector_state: str = ""
    symbol_state: str = ""

    # ===== structure scores =====
    macro_scores: dict[str, float] = field(default_factory=dict)
    sector_scores: dict[str, float] = field(default_factory=dict)
    symbol_scores: dict[str, float] = field(default_factory=dict)

    # ===== key structure variables（给 regime / signal 快速用）=====
    range_position: Optional[float] = None
    trend_slope: Optional[float] = None
    long_slope: Optional[float] = None
    liquidity_quality: Optional[float] = None
    reversal_pressure: Optional[float] = None
    volatility_state: Optional[float] = None
    sector_support_score: Optional[float] = None
    sector_breadth_health: Optional[float] = None
    # ===== snapshots（原始输出，方便 debug / downstream）=====
    macro_snapshot: Any | None = None
    sector_snapshot: Any | None = None
    symbol_snapshot: Any | None = None

    # ===== debug/export only =====
    feature_row: dict[str, Any] | None = None