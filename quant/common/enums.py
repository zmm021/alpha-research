from enum import Enum


class MacroState(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


class SectorState(str, Enum):
    LEADING = "leading"
    MIXED = "mixed"
    WEAK = "weak"


class SymbolState(str, Enum):
    # ===== TREND =====
    TREND_EARLY = "trend_early"                # 刚启动
    TREND_CONTINUATION = "trend_continuation"  # 主升段
    TREND_LATE = "trend_late"                  # 动能减弱
    TREND_EXHAUSTION = "trend_exhaustion"      # 末期 / 过热

    # ===== RANGE =====
    RANGE_ACCUMULATION = "range_accumulation"  # 底部吸筹
    RANGE_NEUTRAL = "range_neutral"            # 中性震荡
    RANGE_DISTRIBUTION = "range_distribution"  # 顶部分布

    # ===== RISK =====
    RISK_RISING = "risk_rising"                # 风险上升
    RISK_HIGH = "risk_high"                    # 高风险（应退出）

    # ===== EVENT / TRANSITION STATES =====
    PULLBACK = "pullback"                      # 趋势回踩
    BREAKOUT_SETUP = "breakout_setup"          # 突破前
    BREAKOUT = "breakout"                      # 突破确认
    BREAKOUT_FAILED = "breakout_failed"        # 假突破

    # ===== STRUCTURE FAILURE =====
    REVERSAL = "reversal"                      # 结构反转
    BREAKDOWN_RISK = "breakdown_risk"          # 下行风险


class ActionSignal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    AVOID = "avoid"


class SetupType(str, Enum):
    TREND_FOLLOW = "trend_follow"
    MEAN_REVERT = "mean_revert"
    BREAKOUT = "breakout"
    DEFENSIVE = "defensive"
    NONE = "none"


class DataQualityState(str, Enum):
    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"

 
class MarketRegime(str, Enum):
    TREND = "trend"
    RANGE = "range"
    RISK = "risk"
    MIXED = "mixed"

class RegimeQuality(Enum):
    STRONG = "strong"
    NORMAL = "normal"
    WEAK = "weak"
    BAD = "bad"
    UNCERTAIN = "uncertain"