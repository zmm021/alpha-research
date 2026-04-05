from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IndicatorLayer(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class IndicatorOwnership(str, Enum):
    SHARED = "shared"
    OFFLINE = "offline"
    ONLINE = "online"


class IndicatorCategory(str, Enum):
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    PRICE_STRUCTURE = "price_structure"
    VOLUME_LIQUIDITY = "volume_liquidity"
    MARKET_BENCHMARK = "market_benchmark"
    MACRO = "macro"
    DECISION = "decision"


class MarketState(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    GOLDEN_CROSS = "golden_cross"
    DEATH_CROSS = "death_cross"
    NONE = "none"


@dataclass(frozen=True)
class IndicatorSpec:
    name: str
    layer: IndicatorLayer
    category: IndicatorCategory
    ownership: IndicatorOwnership
    description: str
    inputs: tuple[str, ...]
    windows: tuple[int, ...] = field(default_factory=tuple)
    params: dict[str, Any] = field(default_factory=dict)