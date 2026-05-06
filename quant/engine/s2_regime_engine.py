from __future__ import annotations

from typing import Optional, Tuple, Any

from quant.common.enums import MarketRegime, RegimeQuality
from quant.engine.context.s1_structure_context import S1StructureContext
from quant.engine.context.s2_regime_context import S2RegimeContext


"""
S2 Regime Engine 市场结构与风险评估层

核心流程：
先定 regime，再评估 quality，最后输出 gating suggestion

1. Base Regime
   根据 slow structure state 判断基础市场模式：
   risk → trend → range → mixed

2. Quality Score
   对当前 regime 进行质量评分：
   TREND:
       趋势强度
       趋势斜率
       macro / sector 支持度
       reversal / volatility 风险

   RANGE:
       区间位置
       short / mid 一致性
       accumulation / distribution 特征

   RISK:
       直接降级为 BAD

3. Gating
   根据：
       regime + regime_quality + macro risk + sector health

   生成交易开关：
       allow_trade, allow_trend, allow_range, risk_off

4. Explain Scores
   输出：
       trend_score, range_score, risk_score

   用于 debug / 解释性分析
"""


# =========================================================
# Structure State → Regime Mapping
# =========================================================

TREND_STRUCTURE_STATES = {
    "trend_early",
    "trend_continuation",
    "trend_late",
    "trend_exhaustion",
    "pullback",
    "breakout_setup",
    "breakout",
    "breakout_failed",
}

RANGE_STRUCTURE_STATES = {
    "range_accumulation",
    "range_neutral",
    "range_distribution",
}

RISK_STRUCTURE_STATES = {
    "risk_rising",
    "risk_high",
    "breakdown_risk",
    "reversal",
}


class RegimeEngine:
    """
    S2 Regime Engine

    核心职责：
        1. 根据 S1 slow symbol_structure_state 判断基础市场模式
        2. 对当前 regime 做 quality score
        3. 输出 allow_trade / allow_trend / allow_range / risk_off
        4. 输出 explain scores，方便 debug

    设计原则：
        - S2 只使用 slow structure
        - fast 留给 S3 Signal / S4 Position / S5 Risk
        - liquidity 暂时只进入 metadata，后续再接入 gating / risk
        - S2 不决定 buy / sell，只决定市场是否适合参与
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def update(self, s1: S1StructureContext) -> S2RegimeContext:
        # =====================================================
        # 1. Read slow states
        # =====================================================
        symbol_structure_state = self._norm(s1.slow_symbol_structure_state)
        symbol_liquidity_state = self._norm(s1.slow_symbol_liquidity_state)
        sector_state = self._norm(s1.slow_sector_state)
        macro_state = self._norm(s1.slow_macro_state)

        # =====================================================
        # 2. Read slow structure values
        # =====================================================
        range_position_short = self._to_float(
            s1.get_symbol_slow("symbol_range_position_short")
        )
        range_position_mid = self._to_float(
            s1.get_symbol_slow("symbol_range_position_mid")
        )

        trend_strength = self._to_float(
            s1.get_symbol_slow("symbol_trend_strength")
        )

        trend_slope = self._to_float(
            s1.get_symbol_slow("symbol_trend_slope")
        )

        reversal_pressure = self._to_float(
            s1.get_symbol_slow("symbol_reversal_pressure")
        )

        volatility_state = self._to_float(
            s1.get_symbol_slow("symbol_volatility_state")
        )

        macro_risk_pressure = self._to_float(
            s1.get_macro_slow("macro_risk_pressure")
        )

        sector_support_score = self._to_float(
            s1.get_sector_slow("sector_support_score")
        )

        sector_breadth_health = self._to_float(
            s1.get_sector_slow("sector_breadth_health")
        )

        # =====================================================
        # 3. Base regime
        # =====================================================
        regime = self._compute_base_regime(
            symbol_structure_state=symbol_structure_state,
            macro_state=macro_state,
        )

        # =====================================================
        # 4. Quality
        # =====================================================
        quality, score = self._compute_quality(
            regime=regime,
            symbol_structure_state=symbol_structure_state,
            sector_state=sector_state,
            macro_state=macro_state,
            range_position_short=range_position_short,
            range_position_mid=range_position_mid,
            trend_strength=trend_strength,
            trend_slope_short=trend_slope,
            trend_slope_mid=trend_slope,
            reversal_pressure=reversal_pressure,
            volatility_state=volatility_state,
            macro_risk_pressure=macro_risk_pressure,
            sector_support_score=sector_support_score,
            sector_breadth_health=sector_breadth_health,
        )

        # =====================================================
        # 5. Gating
        # =====================================================
        allow_trade, allow_trend, allow_range, risk_off, reason = self._compute_gating(
            regime=regime,
            quality=quality,
            symbol_structure_state=symbol_structure_state,
            sector_state=sector_state,
            macro_state=macro_state,
            macro_risk_pressure=macro_risk_pressure,
        )

        # =====================================================
        # 6. Explain scores
        # =====================================================
        trend_score, range_score, risk_score = self._compute_sub_scores(
            symbol_structure_state=symbol_structure_state,
            sector_state=sector_state,
            macro_state=macro_state,
            range_position_short=range_position_short,
            range_position_mid=range_position_mid,
            trend_strength=trend_strength,
            macro_risk_pressure=macro_risk_pressure,
        )

        return S2RegimeContext(
            regime=regime,
            regime_quality=quality,
            regime_score=score,
            trend_score=trend_score,
            range_score=range_score,
            risk_score=risk_score,
            allow_trade=allow_trade,
            allow_trend=allow_trend,
            allow_range=allow_range,
            risk_off=risk_off,
            reason=reason,
            metadata={
                "source": "slow",
                "symbol_structure_state": symbol_structure_state,
                "symbol_liquidity_state": symbol_liquidity_state,
                "sector_state": sector_state,
                "macro_state": macro_state,
                "range_position_short": range_position_short,
                "range_position_mid": range_position_mid,
                "trend_strength": trend_strength,
                "trend_slope": trend_slope,
                "macro_risk_pressure": macro_risk_pressure,
                "sector_support_score": sector_support_score,
                "sector_breadth_health": sector_breadth_health,
            },
        )

    # =====================================================
    # Base regime
    # =====================================================

    def _compute_base_regime(
        self,
        *,
        symbol_structure_state: str,
        macro_state: str,
    ) -> MarketRegime:
        if macro_state == "risk_off":
            return MarketRegime.RISK

        if symbol_structure_state in RISK_STRUCTURE_STATES:
            return MarketRegime.RISK

        if symbol_structure_state in TREND_STRUCTURE_STATES:
            return MarketRegime.TREND

        if symbol_structure_state in RANGE_STRUCTURE_STATES:
            return MarketRegime.RANGE

        return MarketRegime.MIXED

    # =====================================================
    # Quality
    # =====================================================

    def _compute_quality(
        self,
        *,
        regime: MarketRegime,
        symbol_structure_state: str,
        sector_state: str,
        macro_state: str,
        range_position_short: Optional[float],
        range_position_mid: Optional[float],
        trend_strength: Optional[float],
        trend_slope_short: Optional[float],
        trend_slope_mid: Optional[float],
        reversal_pressure: Optional[float],
        volatility_state: Optional[float],
        macro_risk_pressure: Optional[float],
        sector_support_score: Optional[float],
        sector_breadth_health: Optional[float],
    ) -> Tuple[RegimeQuality, float]:

        if regime == MarketRegime.RISK:
            return RegimeQuality.BAD, -1.0

        if regime == MarketRegime.RANGE:
            score = 0.0

            if range_position_short is not None:
                score += 0.6 * self._center_score(range_position_short)

            if range_position_mid is not None:
                score += 0.4 * self._center_score(range_position_mid)

            if range_position_short is not None and range_position_mid is not None:
                diff = abs(range_position_short - range_position_mid)
                score += max(0.0, 0.3 * (1.0 - diff * 2.0))

            if symbol_structure_state == "range_distribution":
                score *= 0.5

            if symbol_structure_state == "range_accumulation":
                score *= 1.1

            if macro_state == "risk_off":
                score = min(score, -0.5)

            if sector_state == "weak":
                score *= 0.5

            score = self._clip(score)
            return self._quality_from_score(score), score

        if regime == MarketRegime.TREND:
            score = 0.3

            if trend_strength is not None:
                score += 0.5 * trend_strength

            if trend_slope_short is not None:
                score += 0.2 * trend_slope_short

            if trend_slope_mid is not None:
                score += 0.5 * trend_slope_mid

            if sector_state == "leading":
                score += 0.2

            if macro_state == "risk_on":
                score += 0.2

            if symbol_structure_state == "trend_exhaustion":
                score *= 0.3

            if symbol_structure_state == "breakout_failed":
                score = -0.5

            if reversal_pressure is not None and reversal_pressure > 0.6:
                score *= 0.5

            if volatility_state is not None and volatility_state > 0.8:
                score *= 0.7

            if macro_risk_pressure is not None and macro_risk_pressure > 0.7:
                score = min(score, -0.5)

            score = self._clip(score)
            return self._quality_from_score(score), score

        return RegimeQuality.UNCERTAIN, 0.0

    # =====================================================
    # Gating
    # =====================================================

    def _compute_gating(
        self,
        *,
        regime: MarketRegime,
        quality: RegimeQuality,
        symbol_structure_state: str,
        sector_state: str,
        macro_state: str,
        macro_risk_pressure: Optional[float],
    ) -> tuple[bool, bool, bool, bool, str]:

        if regime == MarketRegime.RISK:
            return False, False, False, True, "risk_regime"

        if macro_state == "risk_off":
            return False, False, False, True, "macro_risk_off"

        if macro_risk_pressure is not None and macro_risk_pressure >= 0.8:
            return False, False, False, True, "macro_risk_pressure_high"

        if quality in {RegimeQuality.BAD, RegimeQuality.UNCERTAIN}:
            return False, False, False, False, "bad_or_uncertain_quality"

        if sector_state == "weak":
            return False, False, False, False, "sector_weak"

        allow_trade = quality in {RegimeQuality.STRONG, RegimeQuality.NORMAL}
        allow_trend = allow_trade and regime == MarketRegime.TREND
        allow_range = allow_trade and regime == MarketRegime.RANGE

        return allow_trade, allow_trend, allow_range, False, "ok"

    # =====================================================
    # Explain scores
    # =====================================================

    def _compute_sub_scores(
        self,
        *,
        symbol_structure_state: str,
        sector_state: str,
        macro_state: str,
        range_position_short: Optional[float],
        range_position_mid: Optional[float],
        trend_strength: Optional[float],
        macro_risk_pressure: Optional[float],
    ) -> tuple[float, float, float]:

        trend_score = 0.0
        range_score = 0.0
        risk_score = 0.0

        if symbol_structure_state in TREND_STRUCTURE_STATES:
            trend_score += 1.0
        if sector_state == "leading":
            trend_score += 0.3
        if macro_state == "risk_on":
            trend_score += 0.3
        if trend_strength is not None:
            trend_score += max(0.0, trend_strength)

        if symbol_structure_state in RANGE_STRUCTURE_STATES:
            range_score += 1.0
        if range_position_short is not None:
            range_score += self._center_score(range_position_short)
        if range_position_mid is not None:
            range_score += 0.5 * self._center_score(range_position_mid)

        if symbol_structure_state in RISK_STRUCTURE_STATES:
            risk_score += 1.0
        if macro_state == "risk_off":
            risk_score += 1.0
        if macro_risk_pressure is not None:
            risk_score += max(0.0, macro_risk_pressure)

        return trend_score, range_score, risk_score

    # =====================================================
    # Helpers
    # =====================================================

    @staticmethod
    def _norm(v: Any) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value).strip().lower()
        s = str(v).strip().lower()
        if "." in s:
            s = s.split(".")[-1]
        return s

    @staticmethod
    def _to_float(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    @staticmethod
    def _center_score(x: float) -> float:
        x = max(min(float(x), 1.0), 0.0)
        return max(min(1.0 - abs(x - 0.5) * 2.0, 1.0), -1.0)

    @staticmethod
    def _clip(x: float) -> float:
        return max(min(float(x), 1.0), -1.0)

    @staticmethod
    def _quality_from_score(score: float) -> RegimeQuality:
        if score >= 0.65:
            return RegimeQuality.STRONG
        if score >= 0.25:
            return RegimeQuality.NORMAL
        if score >= -0.20:
            return RegimeQuality.WEAK
        return RegimeQuality.BAD


def is_trend(regime: MarketRegime) -> bool:
    return regime == MarketRegime.TREND


def is_range(regime: MarketRegime) -> bool:
    return regime == MarketRegime.RANGE


def is_risk(regime: MarketRegime) -> bool:
    return regime == MarketRegime.RISK


def is_tradable(quality: RegimeQuality) -> bool:
    return quality in {RegimeQuality.STRONG, RegimeQuality.NORMAL}