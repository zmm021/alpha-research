from __future__ import annotations

from dataclasses import dataclass

from quant.engine.decision_context import DecisionContext
from quant.engine.regime_engine import MarketRegime


# =========================================================
# Output
# =========================================================

@dataclass
class PositionProposal:
    """
    Position Engine 输出的“理想行为建议”
    注意：
    - 这不是最终执行结果
    - 最终是否执行、执行多少，由 DecisionEngine 决定
    """
    action: str   # buy / reduce / sell / hold / watch
    qty: int      # 建议单位数量（不是最终股数，DecisionEngine 再乘 base_qty）
    reason: str


# =========================================================
# Position Engine
# =========================================================

class PositionEngine:
    """
    Position Engine:
    - 不看历史表现
    - 不做惩罚
    - 不做风控硬约束
    - 只根据 alpha_signal + regime 给出“仓位行为建议”

    职责：
        signal + regime -> proposal

    最终是否执行、执行多少、是否降级为 HOLD，
    由 DecisionEngine 决定。
    """

    def propose(self, ctx: DecisionContext) -> PositionProposal:
        signal = (ctx.alpha_signal or "").lower()
        regime = ctx.regime
        has_pos = ctx.has_position

        # =========================================================
        # BUY
        # =========================================================
        if signal == "buy":
            if regime == MarketRegime.TREND:
                return PositionProposal(
                    action="buy",
                    qty=1,
                    reason="trend_buy",
                )

            if regime == MarketRegime.RANGE:
                return PositionProposal(
                    action="buy",
                    qty=1,
                    reason="range_buy",
                )

            if regime == MarketRegime.RISK:
                return PositionProposal(
                    action="buy",
                    qty=1,
                    reason="risk_probe_buy",
                )

            return PositionProposal(
                action="hold",
                qty=0,
                reason="unknown_regime_hold",
            )

        # =========================================================
        # REDUCE
        # =========================================================
        if signal == "reduce":
            if not has_pos:
                return PositionProposal(
                    action="hold",
                    qty=0,
                    reason="no_position",
                )

            if regime == MarketRegime.RANGE:
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="range_reduce",
                )

            if regime == MarketRegime.TREND:
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="trim_in_trend",
                )

            if regime == MarketRegime.RISK:
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="defensive_reduce",
                )

            return PositionProposal(
                action="hold",
                qty=0,
                reason="unknown_regime_hold",
            )

        # =========================================================
        # SELL
        # =========================================================
        if signal == "sell":
            if not has_pos:
                return PositionProposal(
                    action="hold",
                    qty=0,
                    reason="no_position",
                )

            return PositionProposal(
                action="sell",
                qty=1,
                reason="alpha_sell",
            )

        # =========================================================
        # AVOID
        # =========================================================
        if signal == "avoid":
            if not has_pos:
                return PositionProposal(
                    action="hold",
                    qty=0,
                    reason="avoid_no_position",
                )

            if regime == MarketRegime.RISK:
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="avoid_reduce_in_risk",
                )

            return PositionProposal(
                action="hold",
                qty=0,
                reason="avoid_hold",
            )

        # =========================================================
        # HOLD / default
        # =========================================================
        return PositionProposal(
            action="hold",
            qty=0,
            reason="default_hold",
        )