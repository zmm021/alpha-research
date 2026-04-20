from __future__ import annotations

from dataclasses import dataclass

from quant.engine.decision_context import DecisionContext
from quant.engine.position_engine import PositionProposal


@dataclass
class FinalDecision:
    action: str
    qty: int
    reason: str


class DecisionEngine:
    """
    最终裁决层：
    - 应用惩罚
    - 控制行为
    - 控制最大仓位
    """

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

        # 1. 防守模式
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

        # 2. reduce 失效，降低做T仓位
        if ctx.disable_reduce and action == "reduce":
            # ❗ 不再完全禁用 reduce
            # 👉 只降低减仓力度（比如减半）
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
        # =========================
        # 🔥 DRAW DOWN RISK CONTROL（新增）
        # =========================
        if ctx.current_drawdown < -1400:
            if action == "buy":
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="drawdown_block_buy",
                )
        # 3. BUY 统一至少 100 股，同时受最大仓位限制
        if action == "buy":
            remaining_capacity = max_position_qty - current_position
            if remaining_capacity <= 0:
                return FinalDecision(
                    action="hold",
                    qty=0,
                    reason="max_position_reached",
                )

            # 不管 cautious 与否，至少/默认都是 100 股
            final_buy_qty = min(base_qty, remaining_capacity)

            # 风险环境下只允许 probe，但 probe 也按 100 股
            if ctx.symbol_state in {"risk_rising", "risk_high", "breakdown_risk"}:
                return FinalDecision(
                    action="buy",
                    qty=final_buy_qty,
                    reason="risk_probe_buy",
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

        # 4. SELL
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

        # 5. REDUCE
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

        # 6. 默认
        return FinalDecision(
            action="hold",
            qty=0,
            reason=f"execute_{proposal.reason}",
        )