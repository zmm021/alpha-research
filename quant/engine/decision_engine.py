from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from quant.engine.decision_context import DecisionContext
from quant.engine.position_engine import PositionProposal
from quant.engine.regime_engine import MarketRegime, RegimeQuality


@dataclass
class FinalDecision:
    action: str
    qty: int
    reason: str


class DecisionEngine:
    """
    最终裁决层：
    - regime / quality filtering
    - drawdown control
    - execution memory（只限制错误重复买）
    """

    BUY_COOLDOWN = timedelta(hours=3)

    def decide(
        self,
        ctx: DecisionContext,
        proposal: PositionProposal,
        base_qty: int = 100,
        max_position_qty: int = 2000,
    ) -> FinalDecision:

        action = proposal.action
        proposed_qty = proposal.qty * base_qty
        current_position = ctx.current_position_qty

        # =====================================================
        # 0️⃣ execution filter（🔥精细版）
        # 只限制“弱结构里的重复 BUY”
        # =====================================================
        if action == "buy":
            if (
                ctx.last_executed_action == "buy"
                and ctx.last_executed_action_time is not None
                and ctx.timestamp is not None
            ):
                dt = ctx.timestamp - ctx.last_executed_action_time

                if dt < self.BUY_COOLDOWN:
                    # ❗只在这些情况下拦
                    if (
                        ctx.regime == MarketRegime.RANGE
                        or ctx.regime == MarketRegime.RISK
                        or ctx.regime_quality in {
                            RegimeQuality.WEAK,
                            RegimeQuality.BAD,
                        }
                    ):
                        return FinalDecision(
                            action="hold",
                            qty=0,
                            reason="repeat_buy_blocked_weak_regime",
                        )

        # =====================================================
        # 1️⃣ 防守模式
        # =====================================================
        if ctx.defensive_mode:
            if ctx.has_position:
                reduce_qty = min(base_qty, current_position)
                if reduce_qty > 0:
                    return FinalDecision(
                        action="reduce",
                        qty=reduce_qty,
                        reason="defensive_reduce",
                    )
            return FinalDecision(
                action="hold",
                qty=0,
                reason="defensive_no_entry",
            )

        # =====================================================
        # 2️⃣ bad range：直接禁止买
        # =====================================================
        if (
            action == "buy"
            and ctx.regime == MarketRegime.RANGE
            and ctx.regime_quality == RegimeQuality.BAD
        ):
            return FinalDecision(
                action="hold",
                qty=0,
                reason="block_bad_range_buy",
            )

        # =====================================================
        # 3️⃣ trend quality 控制
        # =====================================================
        if action == "buy" and ctx.regime == MarketRegime.TREND:

            if ctx.regime_quality == RegimeQuality.BAD:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="block_bad_trend_buy",
                )

            if ctx.regime_quality == RegimeQuality.WEAK:
                remaining_capacity = max_position_qty - current_position

                if remaining_capacity <= 0:
                    return FinalDecision(
                        action="hold",
                        qty=0,
                        reason="max_position_reached",
                    )

                final_buy_qty = min(base_qty, remaining_capacity)
                final_buy_qty = int(final_buy_qty * 0.5)

                if final_buy_qty <= 0:
                    return FinalDecision(
                        action="hold",
                        qty=0,
                        reason="weak_trend_buy_too_small",
                    )

                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="weak_trend_limited_buy",
                )

        # =====================================================
        # 4️⃣ reduce 降级（做T失效）
        # =====================================================
        if ctx.disable_reduce and action == "reduce":
            reduce_qty = min(int(proposed_qty * 0.5), current_position)

            if reduce_qty <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="reduce_blocked_small",
                )

            return FinalDecision(
                action="reduce",
                qty=reduce_qty,
                reason="reduce_limited",
            )

        # =====================================================
        # 5️⃣ drawdown 控制（你当前调优重点）
        # =====================================================
        if ctx.current_drawdown < -900 and action == "buy":

            remaining_capacity = max_position_qty - current_position

            if remaining_capacity <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="max_position_reached",
                )

            # ----- RISK -----
            if ctx.regime == MarketRegime.RISK:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="drawdown_block_risk_buy",
                )

            # ----- RANGE -----
            if ctx.regime == MarketRegime.RANGE:

                if ctx.regime_quality == RegimeQuality.BAD:
                    return FinalDecision(
                        action="hold",
                        qty=0,
                        reason="drawdown_block_bad_range",
                    )

                final_buy_qty = min(base_qty, remaining_capacity)
                final_buy_qty = int(final_buy_qty * 0.5)

                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="drawdown_limited_range",
                )

            # ----- TREND -----
            if ctx.regime == MarketRegime.TREND:

                if ctx.symbol_state in {
                    "trend_late",
                    "trend_exhaustion",
                    "breakout_failed",
                }:
                    return FinalDecision(
                        action="hold",
                        qty=0,
                        reason="drawdown_block_late_trend",
                    )

                final_buy_qty = min(base_qty, remaining_capacity)
                final_buy_qty = int(final_buy_qty * 0.5)

                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="drawdown_limited_trend",
                )

        # =====================================================
        # 6️⃣ BUY（正常路径）
        # =====================================================
        if action == "buy":

            remaining_capacity = max_position_qty - current_position

            if remaining_capacity <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="max_position_reached",
                )

            final_buy_qty = min(base_qty, remaining_capacity)

            if ctx.regime == MarketRegime.RISK:
                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="risk_probe_buy",
                )

            if (
                ctx.regime == MarketRegime.RANGE
                and ctx.regime_quality == RegimeQuality.WEAK
            ):
                final_buy_qty = int(final_buy_qty * 0.5)

                if final_buy_qty <= 0:
                    return FinalDecision(
                        action="hold",
                        qty=0,
                        reason="weak_range_buy_too_small",
                    )

                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="weak_range_limited_buy",
                )

            if ctx.cautious_buy:
                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="cautious_buy",
                )

            return FinalDecision(
                action="buy",
                qty=final_buy_qty,
                reason=f"execute_{proposal.reason}",
            )

        # =====================================================
        # 7️⃣ SELL
        # =====================================================
        if action == "sell":
            sell_qty = min(proposed_qty, current_position)

            if sell_qty <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="no_position",
                )

            return FinalDecision(
                action="sell",
                qty=sell_qty,
                reason=f"execute_{proposal.reason}",
            )

        # =====================================================
        # 8️⃣ REDUCE
        # =====================================================
        if action == "reduce":
            reduce_qty = min(proposed_qty, current_position)

            if reduce_qty <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="no_position",
                )

            return FinalDecision(
                action="reduce",
                qty=reduce_qty,
                reason=f"execute_{proposal.reason}",
            )

        # =====================================================
        # 9️⃣ 默认
        # =====================================================
        return FinalDecision(
            action="hold",
            qty=0,
            reason=f"execute_{proposal.reason}",
        )