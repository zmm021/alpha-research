from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional

import pandas as pd

from quant.symbol.indicator.indicator_state import SymbolIndicatorState
from quant.symbol.factors import compute_symbol_factors, compute_symbol_contexts
from quant.symbol.state import compute_symbol_states


@dataclass
class SymbolSnapshot:
    indicators: Dict[str, Any]
    factors: Dict[str, Any]
    contexts: Dict[str, Any]
    state: str


class SymbolEngine:
    def __init__(self, config: dict):
        self.config = config
        self.indicator_state = SymbolIndicatorState.from_config(config)
        self.prev_state: Optional[str] = None

    def warmup(self, symbol_df):
        self.indicator_state.warmup(symbol_df)
        self.prev_state = None

    def update(self, bar: Dict[str, Any]) -> SymbolSnapshot:
        indicators = self.indicator_state.update(bar)
        indicator_df = pd.DataFrame([indicators])

        factor_df = compute_symbol_factors(
            indicator_df=indicator_df,
            config=self.config,
        )
        context_df = compute_symbol_contexts(
            factor_df=factor_df,
            config=self.config,
        )

        factor_row = factor_df.iloc[0].to_dict()
        context_row = context_df.iloc[0].to_dict()

        state_series = compute_symbol_states(
            context_df=context_df,
            config=self.config,
        )
        state = state_series.iloc[0]

        self.prev_state = state

        return SymbolSnapshot(
            indicators=indicators,
            factors=factor_row,
            contexts=context_row,
            state=state,
        )