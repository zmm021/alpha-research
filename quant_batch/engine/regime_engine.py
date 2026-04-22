from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple


# =========================================================
# Regime Enum（决策层，低维抽象）
# =========================================================

class MarketRegime(str, Enum):
    TREND = "trend"
    RANGE = "range"
    RISK = "risk"
    MIXED = "mixed"


# =========================================================
# Regime Quality
# =========================================================

class RegimeQuality(str, Enum):
    STRONG = "strong"
    NEUTRAL = "neutral"
    WEAK = "weak"
    BAD = "bad"


# =========================================================
# State → Regime Mapping（唯一来源）
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


# =========================================================
# Core API（返回 regime）
# =========================================================

def compute_regime(
    *,
    symbol_state: str,
    sector_state: Optional[str] = None,
    macro_state: Optional[str] = None,
) -> MarketRegime:
    s = (symbol_state or "").lower()

    if s in TREND_STATES:
        base_regime = MarketRegime.TREND
    elif s in RANGE_STATES:
        base_regime = MarketRegime.RANGE
    elif s in RISK_STATES:
        base_regime = MarketRegime.RISK
    else:
        base_regime = MarketRegime.MIXED

    return base_regime


# =========================================================
# Regime Quality（核心）
# =========================================================

def compute_regime_quality(
    *,
    regime: MarketRegime,
    symbol_state: str,
    range_position: Optional[float] = None,
    trend_slope: Optional[float] = None,
    long_slope: Optional[float] = None,
) -> Tuple[RegimeQuality, float]:
    """
    Return:
        (quality_enum, quality_score)

    score ∈ [-1, 1]
    """

    s = (symbol_state or "").lower()

    # =====================================================
    # RANGE QUALITY
    # =====================================================
    if regime == MarketRegime.RANGE:

        if range_position is None:
            return RegimeQuality.NEUTRAL, 0.0

        # 区间中心越稳，质量越高
        center_bias = 1.0 - abs(range_position - 0.5) * 2.0
        score = center_bias

        # 下沉型 range（MP 核心问题）
        if long_slope is not None and long_slope < 0:
            score *= 0.3

        # 顶部分布：质量进一步下降
        if s == "range_distribution":
            score *= 0.3

        # 底部吸筹：稍微加分
        if s == "range_accumulation":
            score *= 1.2

        score = max(min(score, 1.0), -1.0)

        if score >= 0.6:
            return RegimeQuality.STRONG, score
        elif score >= 0.2:
            return RegimeQuality.NEUTRAL, score
        elif score >= -0.2:
            return RegimeQuality.WEAK, score
        else:
            return RegimeQuality.BAD, score

    # =====================================================
    # TREND QUALITY（修正版）
    # =====================================================
    if regime == MarketRegime.TREND:

        # base
        score = 0.5

        # 短期趋势斜率：有帮助，但不能单独决定质量
        if trend_slope is not None:
            score += 0.5 * trend_slope

        # 长期趋势斜率：更重要
        if long_slope is not None:
            score += 1.0 * long_slope

        # trend_exhaustion：显著降级
        if s == "trend_exhaustion":
            score *= 0.3

        # breakout_failed：直接坏
        if s == "breakout_failed":
            score = -0.5

        # pullback：必须依赖 long_slope 判断是不是健康回踩
        if s == "pullback":
            if long_slope is not None and long_slope < 0:
                # 下行结构中的反弹，不应被视作强趋势
                score *= 0.3

        # 长期方向为负时，不允许 strong
        if long_slope is not None and long_slope < 0:
            score = min(score, 0.4)

        score = max(min(score, 1.0), -1.0)

        if score >= 0.6:
            return RegimeQuality.STRONG, score
        elif score >= 0.2:
            return RegimeQuality.NEUTRAL, score
        elif score >= -0.2:
            return RegimeQuality.WEAK, score
        else:
            return RegimeQuality.BAD, score

    # =====================================================
    # RISK QUALITY
    # =====================================================
    if regime == MarketRegime.RISK:
        return RegimeQuality.BAD, -1.0

    return RegimeQuality.NEUTRAL, 0.0


# =========================================================
# Combined API
# =========================================================

def compute_regime_with_quality(
    *,
    symbol_state: str,
    sector_state: Optional[str] = None,
    macro_state: Optional[str] = None,
    range_position: Optional[float] = None,
    trend_slope: Optional[float] = None,
    long_slope: Optional[float] = None,
):
    regime = compute_regime(
        symbol_state=symbol_state,
        sector_state=sector_state,
        macro_state=macro_state,
    )

    quality, score = compute_regime_quality(
        regime=regime,
        symbol_state=symbol_state,
        range_position=range_position,
        trend_slope=trend_slope,
        long_slope=long_slope,
    )

    return regime, quality, score


# =========================================================
# Helper Functions
# =========================================================

def is_trend(regime: MarketRegime) -> bool:
    return regime == MarketRegime.TREND


def is_range(regime: MarketRegime) -> bool:
    return regime == MarketRegime.RANGE


def is_risk(regime: MarketRegime) -> bool:
    return regime == MarketRegime.RISK


def is_tradable(quality: RegimeQuality) -> bool:
    return quality in {RegimeQuality.STRONG, RegimeQuality.NEUTRAL}