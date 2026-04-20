from __future__ import annotations

from dataclasses import dataclass

from quant.engine.decision_context import DecisionContext


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
# Regime Helpers
# =========================================================

def _is_trend_state(state: str) -> bool:
    return state in {
        "trend_early",
        "trend_continuation",
        "trend_late",
        "trend_exhaustion",
        "pullback",
        "breakout_setup",
        "breakout",
        "breakout_failed",
    }


def _is_range_state(state: str) -> bool:
    return state in {
        "range_accumulation",
        "range_neutral",
        "range_distribution",
    }


def _is_risk_state(state: str) -> bool:
    return state in {
        "risk_rising",
        "risk_high",
        "breakdown_risk",
    }


# =========================================================
# Position Engine
# =========================================================

class PositionEngine:
    """
    Position Engine:
    - 不看历史表现
    - 不做惩罚
    - 不做风控硬约束
    - 只根据 alpha_signal + symbol_state 给出“仓位行为建议”

    职责：
        signal + regime -> proposal

    最终是否执行、执行多少、是否降级为 HOLD，
    由 DecisionEngine 决定。
    """

    def propose(self, ctx: DecisionContext) -> PositionProposal:
        signal = (ctx.alpha_signal or "").lower()
        regime = (ctx.symbol_state or "").lower()
        has_pos = ctx.has_position

        # =========================================================
        # BUY
        # =========================================================
        if signal == "buy":
            # 趋势/突破类环境：正常允许买
            if _is_trend_state(regime):
                return PositionProposal(
                    action="buy",
                    qty=1,
                    reason="trend_buy",
                )

            # 震荡环境：允许买，后续看 decision 是否放行
            if _is_range_state(regime):
                return PositionProposal(
                    action="buy",
                    qty=1,
                    reason="range_buy",
                )

            # 风险环境：这里只给 probe suggestion，最终交给 decision engine
            if _is_risk_state(regime):
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

            # 震荡环境：做T最合理
            if _is_range_state(regime):
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="range_reduce",
                )

            # 趋势环境：reduce 更像是 trim，不一定是错
            if _is_trend_state(regime):
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="trim_in_trend",
                )

            # 风险环境：reduce 更偏防守性
            if _is_risk_state(regime):
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

            # 在风险环境下，avoid 对持仓不应只是中性
            if _is_risk_state(regime):
                return PositionProposal(
                    action="reduce",
                    qty=1,
                    reason="avoid_reduce_in_risk",
                )

            # 其他环境里，avoid 先解释成 hold
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