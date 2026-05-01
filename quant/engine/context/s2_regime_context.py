from __future__ import annotations

from dataclasses import dataclass

from quant.common.enums import MarketRegime, RegimeQuality


@dataclass
class S2RegimeContext:
    """
    S2: 市场模式层（跨层聚合）

    来源：
        RegimeEngine

    依赖：
        S1StructureContext
    """

    # ===== core regime =====
    regime: MarketRegime | None = None
    regime_quality: RegimeQuality | None = None
    regime_score: float = 0.0

    # ===== gating（非常关键，后面 signal / position 会用）=====
    allow_trade: bool = True
    allow_trend: bool = True
    allow_range: bool = True
    risk_off: bool = False