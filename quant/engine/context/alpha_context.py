from dataclasses import dataclass, field

from quant.engine.context.s1_structure_context import S1StructureContext
from quant.engine.context.s2_regime_context import S2RegimeContext
from quant.engine.context.s3_signal_context import S3SignalContext
from quant.engine.context.s4_position_context import S4PositionContext
from quant.engine.context.s5_risk_context import S5RiskContext
from quant.engine.context.s6_decision_context import S6DecisionContext


@dataclass
class AlphaContext:
    symbol: str
    timestamp: object | None
    price: float

    s1_structure: S1StructureContext = field(default_factory=S1StructureContext)
    s2_regime: S2RegimeContext = field(default_factory=S2RegimeContext)

    s3_signal: S3SignalContext = field(default_factory=S3SignalContext)
    s4_position: S4PositionContext = field(default_factory=S4PositionContext)
    s5_risk: S5RiskContext = field(default_factory=S5RiskContext)
    s6_decision: S6DecisionContext = field(default_factory=S6DecisionContext)