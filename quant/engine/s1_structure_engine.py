from __future__ import annotations

from typing import Any

from quant.symbol.symbol_engine import SymbolEngine
from quant.engine.context.alpha_context import AlphaContext
from quant.engine.context.s1_structure_context import S1StructureContext


class S1StructureEngine:
    """
    S1 Structure Engine

    Responsibilities:
        - manage runtime symbol fast engine
        - warmup symbol fast rolling state
        - update symbol fast on each new bar
        - merge fast output into existing S1 slow context

    Important:
        - does NOT load slow data from Postgres
        - does NOT compute macro / sector
        - slow data should be loaded by S1SlowLoader outside this engine
    """

    def __init__(self, config: dict):
        self.symbol_engine = SymbolEngine(config["symbol"])

    def warmup(self, symbol_df) -> None:
        """
        Warm up runtime symbol fast engine once.
        """
        self.symbol_engine.warmup(symbol_df)

    def update(
        self,
        *,
        ctx: AlphaContext,
        symbol_bar: dict[str, Any],
    ) -> S1StructureContext:
        """
        Update S1 for one new bar.

        Expected flow before calling this:
            S1SlowLoader has already populated ctx.s1_structure
            when as_of_date changed.

        This method only adds / refreshes symbol fast data.
        """
        if ctx.s1_structure is None:
            raise ValueError(
                "ctx.s1_structure is None. "
                "S1SlowLoader must load slow context before S1StructureEngine.update()."
            )

        s1 = ctx.s1_structure

        symbol_snapshot = self.symbol_engine.update(symbol_bar)

        s1.symbol = ctx.symbol
        s1.sector_name = ctx.sector
        s1.timestamp = ctx.timestamp

        # fast runtime states
        s1.symbol_structure_state = self._to_str(
            symbol_snapshot.symbol_structure_state
        )
        s1.symbol_liquidity_state = self._to_str(
            symbol_snapshot.symbol_liquidity_state
        )

        # fast runtime data
        s1.symbol_fast = {
            "indicators": symbol_snapshot.indicators,
            "factors": symbol_snapshot.factors,
            "structure_scores": symbol_snapshot.structure_scores,
            "symbol_structure_state": self._to_str(
                symbol_snapshot.symbol_structure_state
            ),
            "symbol_liquidity_state": self._to_str(
                symbol_snapshot.symbol_liquidity_state
            ),
        }

        # debug
        s1.symbol_snapshot = symbol_snapshot

        ctx.s1_structure = s1
        return s1

    @staticmethod
    def _to_str(v) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)