from __future__ import annotations

from dataclasses import dataclass, field

from quant.common.enums import MarketRegime, RegimeQuality


@dataclass
class S2RegimeContext:
    """
    S2: 市场模式层（跨层聚合）

    来源：
        RegimeEngine

    依赖：
        S1StructureContext

    职责：
        1. 压缩 S1 结构信息为 market regime
        2. 输出交易 gating
        3. 保留解释信息，方便 debug / 回测分析
    """

    # ===== core regime =====
    regime: MarketRegime = MarketRegime.MIXED
    regime_quality: RegimeQuality = RegimeQuality.UNCERTAIN
    regime_score: float = 0.0

    # ===== sub scores（debug / explain）=====
    trend_score: float = 0.0
    range_score: float = 0.0
    risk_score: float = 0.0

    # ===== gating =====
    allow_trade: bool = False
    allow_trend: bool = False
    allow_range: bool = False
    risk_off: bool = False

    # ===== reason / metadata =====
    reason: str = ""
    metadata: dict = field(default_factory=dict)