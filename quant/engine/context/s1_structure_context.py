from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class S1StructureContext:
    """
    S1: 结构层（L2 输出统一承载）

    来源：
        MacroEngine / SectorEngine / SymbolEngine

    承载：
        1. 各层 state（macro / sector / symbol）
        2. 各层 structure scores（完整信息）
        3. 多尺度关键结构变量（供 S2 / L3 使用）
        4. snapshot（debug / 可解释性）
    """

    # ==========================================
    # ===== states =====
    # ==========================================
    macro_state: str = ""
    sector_state: str = ""
    symbol_state: str = ""

    # ==========================================
    # ===== full structure scores（完整信息，不丢）=====
    # ==========================================
    macro_scores: dict[str, float] = field(default_factory=dict)
    sector_scores: dict[str, float] = field(default_factory=dict)
    symbol_scores: dict[str, float] = field(default_factory=dict)

    # ==========================================
    # ===== key structure variables（multi-scale）=====
    # 👉 给 regime / signal 快速使用
    # ==========================================

    # ---- range（核心，多尺度）----
    range_position_short: Optional[float] = None
    range_position_mid: Optional[float] = None

    # ---- trend ----
    trend_slope_short: Optional[float] = None
    trend_slope_mid: Optional[float] = None
    trend_strength: Optional[float] = None

    # ---- risk / quality ----
    liquidity_quality: Optional[float] = None
    reversal_pressure: Optional[float] = None
    volatility_state: Optional[float] = None

    # ---- macro / sector shortcuts（可选但实用）----
    macro_risk_pressure: Optional[float] = None

    sector_support_score: Optional[float] = None
    sector_breadth_health: Optional[float] = None

    # ==========================================
    # ===== snapshots（原始输出，debug 用）=====
    # ==========================================
    macro_snapshot: Any | None = None
    sector_snapshot: Any | None = None
    symbol_snapshot: Any | None = None

    # ==========================================
    # ===== debug / export =====
    # ==========================================
    feature_row: dict[str, Any] | None = None

"""
🧠 Alpha Stack – S1 Structure Context

S1 是系统的“结构统一层”，负责承载所有 L2（structure）信息，并向上游（S2 / Signal / Position）提供统一接口。

--------------------------------------
📦 数据来源（在哪里看完整定义）

所有结构信息来自三层：

1️⃣ Indicators（L1 原始层）
    定义位置：
        quant/common/constants.py → class Indicators
        quant/symbol/indicator/*.py
        quant/sector/indicator/*.py
        quant/macro/indicator/*.py

    内容：
        - price / MA / ATR / volume / range 等基础统计量

--------------------------------------

2️⃣ Factors（L2a 因子层）
    定义位置：
        quant/common/constants.py → class Factors
        quant/*/factor/*.py

    内容：
        - trend_factor
        - volatility_factor
        - liquidity_factor
        - position_factor
        - intraday_factor
        等（对 indicators 的抽象）

--------------------------------------

3️⃣ StructureScores（L2b 结构层）
    定义位置：
        quant/common/constants.py → class StructureScores
        quant/*/factor/structure.py

    内容：
        - trend_strength
        - range_position_short / mid
        - reversal_pressure
        - exhaustion_risk
        - macro_risk_pressure
        等（用于状态与决策的核心变量）

--------------------------------------

🧩 S1 的职责

S1 并不产生新信息，它只做三件事：

1. 聚合三层输出（macro / sector / symbol）
2. 保留完整 structure scores（不丢信息）
3. 提供“关键变量快捷访问”（避免下游频繁 dict lookup）

--------------------------------------

🔑 设计原则

- StructureScores = 全量数据（单一事实源）
- S1 fields = 下游决策使用的精选变量（快路径）
- snapshot = debug / 可解释性

--------------------------------------

⚠️ 注意

- 不要在 S1 重新计算指标
- 不要在 S1 引入策略逻辑
- S1 是纯结构层（structure only）

--------------------------------------

🎯 一句话总结

S1 是：
    “结构数据的统一接口（API）”
而不是：
    “计算层”
"""