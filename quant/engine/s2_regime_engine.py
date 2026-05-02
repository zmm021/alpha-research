from __future__ import annotations

from typing import Optional, Tuple

from quant.common.enums import MarketRegime, RegimeQuality
from quant.engine.context.s1_structure_context import S1StructureContext
from quant.engine.context.s2_regime_context import S2RegimeContext


# =========================================================
# State → Regime Mapping
# =========================================================

TREND_STATES = {
    "trend_early",
    "trend_continuation",
    "trend_late",
    "trend_exhaustion",
    "pullback",
    "breakout_setup",
    "breakout",
    "breakout_failed",
}

RANGE_STATES = {
    "range_accumulation",
    "range_neutral",
    "range_distribution",
}

RISK_STATES = {
    "risk_rising",
    "risk_high",
    "breakdown_risk",
    "reversal",
}


class RegimeEngine:
    """
    S2 Regime Engine

    Input:
        S1StructureContext

    Output:
        S2RegimeContext

    Core idea:
        S1 = detailed structure
        S2 = compressed market regime + gating
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def update(self, s1: S1StructureContext) -> S2RegimeContext:
        symbol_state = self._norm(s1.symbol_state)
        sector_state = self._norm(s1.sector_state)
        macro_state = self._norm(s1.macro_state)

        regime = self._compute_base_regime(
            symbol_state=symbol_state,
            macro_state=macro_state,
        )

        quality, score = self._compute_quality(
            regime=regime,
            symbol_state=symbol_state,
            sector_state=sector_state,
            macro_state=macro_state,
            range_position_short=s1.range_position_short,
            range_position_mid=s1.range_position_mid,
            trend_strength=s1.trend_strength,
            trend_slope_short=s1.trend_slope_short,
            trend_slope_mid=s1.trend_slope_mid,
            reversal_pressure=s1.reversal_pressure,
            volatility_state=s1.volatility_state,
            macro_risk_pressure=s1.macro_risk_pressure,
            sector_support_score=s1.sector_support_score,
            sector_breadth_health=s1.sector_breadth_health,
        )

        allow_trade, allow_trend, allow_range, risk_off, reason = self._compute_gating(
            regime=regime,
            quality=quality,
            symbol_state=symbol_state,
            sector_state=sector_state,
            macro_state=macro_state,
            macro_risk_pressure=s1.macro_risk_pressure,
        )

        trend_score, range_score, risk_score = self._compute_sub_scores(
            symbol_state=symbol_state,
            sector_state=sector_state,
            macro_state=macro_state,
            range_position_short=s1.range_position_short,
            range_position_mid=s1.range_position_mid,
            trend_strength=s1.trend_strength,
            macro_risk_pressure=s1.macro_risk_pressure,
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
                "symbol_state": symbol_state,
                "sector_state": sector_state,
                "macro_state": macro_state,
            },
        )

    # =====================================================
    # Base regime
    # =====================================================

    def _compute_base_regime(
        self,
        *,
        symbol_state: str,
        macro_state: str,
    ) -> MarketRegime:
        if macro_state == "risk_off":
            return MarketRegime.RISK

        if symbol_state in RISK_STATES:
            return MarketRegime.RISK

        if symbol_state in TREND_STATES:
            return MarketRegime.TREND

        if symbol_state in RANGE_STATES:
            return MarketRegime.RANGE

        return MarketRegime.MIXED

    # =====================================================
    # Quality
    # =====================================================

    def _compute_quality(
        self,
        *,
        regime: MarketRegime,
        symbol_state: str,
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

            if symbol_state == "range_distribution":
                score *= 0.5

            if symbol_state == "range_accumulation":
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

            if symbol_state == "trend_exhaustion":
                score *= 0.3

            if symbol_state == "breakout_failed":
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
        symbol_state: str,
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
        symbol_state: str,
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

        if symbol_state in TREND_STATES:
            trend_score += 1.0
        if sector_state == "leading":
            trend_score += 0.3
        if macro_state == "risk_on":
            trend_score += 0.3
        if trend_strength is not None:
            trend_score += max(0.0, trend_strength)

        if symbol_state in RANGE_STATES:
            range_score += 1.0
        if range_position_short is not None:
            range_score += self._center_score(range_position_short)
        if range_position_mid is not None:
            range_score += 0.5 * self._center_score(range_position_mid)

        if symbol_state in RISK_STATES:
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
    def _safe_float(v, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

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