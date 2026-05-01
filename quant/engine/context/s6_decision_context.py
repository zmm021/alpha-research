from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S6DecisionContext:
    action: str = ""
    qty: int = 0
    reason: str = ""

    executed: bool = False
    executed_qty: int = 0
    executed_price: float | None = None
    execution_time: object | None = None