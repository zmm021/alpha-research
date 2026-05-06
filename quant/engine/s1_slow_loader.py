from __future__ import annotations

from typing import Any

from postgres.daily_structure_repo import get_latest_daily_structure_bundle
from quant.engine.context.alpha_context import AlphaContext
from quant.engine.context.s1_structure_context import S1StructureContext


class S1SlowLoader:
    """
    Load daily slow structure from Postgres and build the slow part of S1StructureContext.

    Rules:
        - macro / sector / symbol slow data all come from DB
        - as_of_date is the slow alignment date
        - loader does not compute indicators
        - loader does not touch fast symbol data
    """

    def load(self, ctx: AlphaContext) -> S1StructureContext:
        if ctx.as_of_date is None:
            raise ValueError("AlphaContext.as_of_date is required for S1SlowLoader")

        if not ctx.symbol:
            raise ValueError("AlphaContext.symbol is required for S1SlowLoader")

        if not ctx.sector:
            raise ValueError("AlphaContext.sector is required for S1SlowLoader")

        bundle = get_latest_daily_structure_bundle(
            symbol=ctx.symbol,
            sector_name=ctx.sector,
            as_of_date=ctx.as_of_date,
        )

        macro_row = bundle.get("macro")
        sector_row = bundle.get("sector")
        symbol_row = bundle.get("symbol")

        if macro_row is None:
            raise ValueError(
                f"Missing macro slow structure for as_of_date={ctx.as_of_date}"
            )

        if sector_row is None:
            raise ValueError(
                f"Missing sector slow structure for sector={ctx.sector}, "
                f"as_of_date={ctx.as_of_date}"
            )

        if symbol_row is None:
            raise ValueError(
                f"Missing symbol slow structure for symbol={ctx.symbol}, "
                f"as_of_date={ctx.as_of_date}"
            )

        s1 = S1StructureContext(
            symbol=ctx.symbol,
            sector_name=ctx.sector,
            timestamp=ctx.timestamp,

            slow_macro_state=str(macro_row.get("macro_state") or ""),
            slow_sector_state=str(sector_row.get("sector_state") or ""),

            slow_symbol_structure_state=str(
                symbol_row.get("symbol_structure_state") or ""
            ),
            slow_symbol_liquidity_state=str(
                symbol_row.get("symbol_liquidity_state") or ""
            ),

            macro_slow=self._clean_row(macro_row),
            sector_slow=self._clean_row(sector_row),
            symbol_slow=self._clean_row(symbol_row),

            slow_bundle=bundle,
        )

        ctx.s1_structure = s1
        return s1

    @staticmethod
    def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
        exclude = {
            "created_at",
            "updated_at",
        }

        return {
            k: v
            for k, v in row.items()
            if k not in exclude
        }