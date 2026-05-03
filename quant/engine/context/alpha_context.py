from dataclasses import dataclass
from datetime import date, datetime

from quant.engine.context.s1_structure_context import S1StructureContext
from quant.engine.context.s2_regime_context import S2RegimeContext
from quant.engine.context.s3_signal_context import S3SignalContext
from quant.engine.context.s4_position_context import S4PositionContext
from quant.engine.context.s5_risk_context import S5RiskContext
from quant.engine.context.s6_decision_context import S6DecisionContext


@dataclass
class AlphaContext:
    symbol: str
    sector: str

    # ===== time alignment =====
    timestamp: datetime | None = None   # 当前 bar 时间（intraday）
    as_of_date: date | None = None      # slow 对齐日期（通常 T-1）

    # ===== execution =====
    price: float | None = None

    # ===== layered context =====
    s1_structure: S1StructureContext | None = None
    s2_regime: S2RegimeContext | None = None

    s3_signal: S3SignalContext | None = None
    s4_position: S4PositionContext | None = None
    s5_risk: S5RiskContext | None = None
    s6_decision: S6DecisionContext | None = None