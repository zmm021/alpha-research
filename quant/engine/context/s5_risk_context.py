from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S5RiskContext:
    defensive_mode: bool = False

    risk_action: str = ""
    risk_reason: str = ""
    risk_priority: int = 0

    force_exit: bool = False
    block_buy: bool = False
    block_reduce: bool = False
    max_allowed_position: int | None = None