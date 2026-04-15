from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quant.common.enums import (
    DataQualityState,
    MacroState,
    SectorState,
    SymbolState,
)


@dataclass(slots=True)
class IndicatorOutput:
    values: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float | None = None) -> float | None:
        return self.values.get(name, default)

    def require(self, name: str) -> float:
        if name not in self.values:
            raise KeyError(f"Missing indicator: {name}")
        return self.values[name]


@dataclass(slots=True)
class FactorOutput:
    values: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float | None = None) -> float | None:
        return self.values.get(name, default)

    def require(self, name: str) -> float:
        if name not in self.values:
            raise KeyError(f"Missing factor: {name}")
        return self.values[name]


@dataclass(slots=True)
class ContextOutput:
    values: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float | None = None) -> float | None:
        return self.values.get(name, default)

    def require(self, name: str) -> float:
        if name not in self.values:
            raise KeyError(f"Missing context: {name}")
        return self.values[name]


@dataclass(slots=True)
class StateOutput:
    macro_state: MacroState = MacroState.NEUTRAL
    sector_state: SectorState = SectorState.MIXED
    symbol_state: SymbolState = SymbolState.RANGE
    data_quality_state: DataQualityState = DataQualityState.OK


@dataclass(slots=True)
class LayerSnapshot:
    timestamp: Any
    symbol: str | None = None

    indicators: IndicatorOutput = field(default_factory=IndicatorOutput)
    factors: FactorOutput = field(default_factory=FactorOutput)
    contexts: ContextOutput = field(default_factory=ContextOutput)
    states: StateOutput = field(default_factory=StateOutput)

    metadata: dict[str, Any] = field(default_factory=dict)