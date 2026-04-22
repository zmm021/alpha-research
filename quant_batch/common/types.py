from __future__ import annotations

from typing import Any, Mapping, MutableMapping

Numeric = float
SeriesLike = Any

IndicatorMap = Mapping[str, Numeric]
MutableIndicatorMap = MutableMapping[str, Numeric]

FactorMap = Mapping[str, Numeric]
MutableFactorMap = MutableMapping[str, Numeric]

ContextMap = Mapping[str, Numeric]
MutableContextMap = MutableMapping[str, Numeric]

ConfigDict = dict[str, Any]