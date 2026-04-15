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
    TREND = "trend"
    PULLBACK = "pullback"
    RANGE = "range"
    BREAKOUT_SETUP = "breakout_setup"
    EXHAUSTED = "exhausted"
    BREAKDOWN_RISK = "breakdown_risk"
    HIGH_RISK = "high_risk"


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