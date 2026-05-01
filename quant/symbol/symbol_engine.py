from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional

import pandas as pd

from quant.symbol.indicator.indicator_state import SymbolIndicatorState
from quant.symbol.factors import compute_symbol_factors, compute_symbol_structure
from quant.symbol.state import compute_symbol_state_output
from quant.common.schemas import StructureOutput


@dataclass
class SymbolSnapshot:
    indicators: Dict[str, Any]
    factors: Dict[str, Any]
    structure_scores: Dict[str, Any]
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
        # ===== indicators =====
        indicators = self.indicator_state.update(bar)
        indicator_df = pd.DataFrame([indicators])

        # ===== factors =====
        factor_df = compute_symbol_factors(
            indicator_df=indicator_df,
            config=self.config,
        )

        # ===== structure scores =====
        structure_df = compute_symbol_structure(
            factor_df=factor_df,
            config=self.config,
        )

        factor_row = factor_df.iloc[0].to_dict()
        structure_row = structure_df.iloc[0].to_dict()

        # ===== state =====
        structure_output = StructureOutput(values=structure_row)

        state = compute_symbol_state_output(
            structure_output=structure_output,
            config=self.config,
        )

        self.prev_state = state

        return SymbolSnapshot(
            indicators=indicators,
            factors=factor_row,
            structure_scores=structure_row,
            state=state,
        )