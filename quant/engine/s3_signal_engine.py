from __future__ import annotations

from datetime import timedelta
from typing import Any

from quant.common.enums import ActionSignal, MarketRegime
from quant.engine.context.s1_structure_context import S1StructureContext
from quant.engine.context.s2_regime_context import S2RegimeContext
from quant.engine.context.s3_signal_context import S3SignalContext


class SignalEngine:
    def __init__(self, config: dict):
        self.config = config.get("signal", config)

        self.enable_cooldown = bool(self.config.get("enable_cooldown", True))
        self.buy_to_exit_cooldown = timedelta(
            hours=float(self.config.get("buy_to_exit_cooldown_hours", 3))
        )
        self.exit_to_buy_cooldown = timedelta(
            hours=float(self.config.get("exit_to_buy_cooldown_hours", 3))
        )
        self.emit_only_on_switch = bool(self.config.get("emit_only_on_switch", True))

    def update(
        self,
        *,
        timestamp: Any,
        s1: S1StructureContext,
        s2: S2RegimeContext,
        prev_s3: S3SignalContext | None = None,
    ) -> S3SignalContext:
        raw_signal, reason, priority = self._compute_raw_signal(s1, s2)

        gated_signal = self._apply_gating(raw_signal, s2)
        cooled_signal, cooldown_active = self._apply_cooldown(
            signal=gated_signal,
            timestamp=timestamp,
            prev_s3=prev_s3,
        )

        final_signal = self._collapse_repeated_signal(cooled_signal, prev_s3)

        new_s3 = S3SignalContext(
            alpha_signal=self._to_value(final_signal),
            raw_signal=self._to_value(raw_signal),
            signal_reason=reason,
            signal_priority=priority,
            allow_trade=s2.allow_trade,
            allow_buy=s2.allow_trade and final_signal == ActionSignal.BUY,
            allow_reduce=s2.allow_trade and final_signal == ActionSignal.REDUCE,
            allow_sell=s2.allow_trade and final_signal == ActionSignal.SELL,
            last_emitted_signal=(
                self._to_value(final_signal)
                if final_signal in {ActionSignal.BUY, ActionSignal.SELL, ActionSignal.REDUCE, ActionSignal.AVOID}
                else (prev_s3.last_emitted_signal if prev_s3 else None)
            ),
            last_action_signal=(
                self._to_value(final_signal)
                if final_signal in {ActionSignal.BUY, ActionSignal.SELL, ActionSignal.REDUCE}
                else (prev_s3.last_action_signal if prev_s3 else None)
            ),
            last_action_time=(
                timestamp
                if final_signal in {ActionSignal.BUY, ActionSignal.SELL, ActionSignal.REDUCE}
                else (prev_s3.last_action_time if prev_s3 else None)
            ),
            cooldown_active=cooldown_active,
            metadata={
                "regime": self._to_value(s2.regime),
                "regime_quality": self._to_value(s2.regime_quality),
                "symbol_state": s1.symbol_state,
                "sector_state": s1.sector_state,
                "macro_state": s1.macro_state,
            },
        )

        return new_s3

    def _compute_raw_signal(
        self,
        s1: S1StructureContext,
        s2: S2RegimeContext,
    ) -> tuple[ActionSignal, str, int]:
        if s2.risk_off or s2.regime == MarketRegime.RISK:
            return self._risk_signal(s1)

        if s2.regime == MarketRegime.TREND and s2.allow_trend:
            return self._trend_signal(s1)

        if s2.regime == MarketRegime.RANGE and s2.allow_range:
            return self._range_signal(s1)

        return ActionSignal.HOLD, "mixed_or_not_allowed", 0

    def _trend_signal(self, s1: S1StructureContext) -> tuple[ActionSignal, str, int]:
        state = self._norm(s1.symbol_state)

        if state in {"trend_early", "pullback", "breakout_setup", "breakout"}:
            return ActionSignal.BUY, f"trend_buy:{state}", 80

        if state in {"trend_continuation"}:
            return ActionSignal.HOLD, "trend_continuation_hold", 50

        if state in {"trend_late", "trend_exhaustion"}:
            return ActionSignal.REDUCE, f"trend_reduce:{state}", 70

        if state == "breakout_failed":
            return ActionSignal.SELL, "breakout_failed", 90

        return ActionSignal.HOLD, "trend_default_hold", 0

    def _range_signal(self, s1: S1StructureContext) -> tuple[ActionSignal, str, int]:
        rp = s1.range_position_short

        if rp is None:
            return ActionSignal.HOLD, "range_position_short_not_ready", 0

        buy_th = float(self.config.get("range_buy_position_threshold", 0.30))
        reduce_th = float(self.config.get("range_reduce_position_threshold", 0.70))
        sell_th = float(self.config.get("range_sell_position_threshold", 0.85))

        if rp <= buy_th:
            return ActionSignal.BUY, "range_low_buy", 70

        if rp >= sell_th:
            return ActionSignal.SELL, "range_upper_sell", 80

        if rp >= reduce_th:
            return ActionSignal.REDUCE, "range_upper_reduce", 60

        return ActionSignal.HOLD, "range_middle_hold", 0

    def _risk_signal(self, s1: S1StructureContext) -> tuple[ActionSignal, str, int]:
        state = self._norm(s1.symbol_state)

        if state in {"risk_high", "breakdown_risk"}:
            action = self._parse_action(
                self.config.get("high_risk_action", "sell")
            ) or ActionSignal.SELL
            return action, f"hard_risk:{state}", 100

        if state in {"risk_rising", "trend_late", "trend_exhaustion"}:
            action = self._parse_action(
                self.config.get("exhausted_action", "reduce")
            ) or ActionSignal.REDUCE
            return action, f"risk_reduce:{state}", 90

        action = self._parse_action(
            self.config.get("risk_off_action", "avoid")
        ) or ActionSignal.AVOID
        return action, "risk_regime_action", 80

    def _apply_gating(
        self,
        signal: ActionSignal,
        s2: S2RegimeContext,
    ) -> ActionSignal:
        if not s2.allow_trade:
            if signal == ActionSignal.BUY:
                return ActionSignal.AVOID
            if signal in {ActionSignal.REDUCE, ActionSignal.SELL}:
                return signal
            return ActionSignal.HOLD

        if signal == ActionSignal.BUY:
            if s2.regime == MarketRegime.TREND and not s2.allow_trend:
                return ActionSignal.HOLD
            if s2.regime == MarketRegime.RANGE and not s2.allow_range:
                return ActionSignal.HOLD

        return signal

    def _apply_cooldown(
        self,
        *,
        signal: ActionSignal,
        timestamp: Any,
        prev_s3: S3SignalContext | None,
    ) -> tuple[ActionSignal, bool]:
        if not self.enable_cooldown or prev_s3 is None:
            return signal, False

        last_action = self._parse_action(prev_s3.last_action_signal)
        last_time = prev_s3.last_action_time

        if last_action is None or last_time is None:
            return signal, False

        try:
            diff = timestamp - last_time
        except Exception:
            return signal, False

        if last_action == ActionSignal.BUY:
            if diff < self.buy_to_exit_cooldown and signal in {ActionSignal.REDUCE, ActionSignal.SELL}:
                return ActionSignal.HOLD, True

        if last_action in {ActionSignal.SELL, ActionSignal.REDUCE}:
            if diff < self.exit_to_buy_cooldown and signal == ActionSignal.BUY:
                return ActionSignal.HOLD, True

        return signal, False

    def _collapse_repeated_signal(
        self,
        signal: ActionSignal,
        prev_s3: S3SignalContext | None,
    ) -> ActionSignal:
        if not self.emit_only_on_switch:
            return signal

        if signal == ActionSignal.HOLD:
            return signal

        if prev_s3 is None or not prev_s3.last_emitted_signal:
            return signal

        last_emitted = self._parse_action(prev_s3.last_emitted_signal)

        if last_emitted == signal:
            return ActionSignal.HOLD

        return signal

    @staticmethod
    def _norm(v) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value).strip().lower()
        s = str(v).strip().lower()
        if "." in s:
            s = s.split(".")[-1]
        return s

    @staticmethod
    def _parse_action(v) -> ActionSignal | None:
        if v is None or v == "":
            return None
        if isinstance(v, ActionSignal):
            return v
        try:
            return ActionSignal(str(v).lower())
        except Exception:
            return None

    @staticmethod
    def _to_value(v) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)