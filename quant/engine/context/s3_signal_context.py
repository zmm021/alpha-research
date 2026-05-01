from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S3SignalContext:
    alpha_signal: str = ""
    signal_reason: str = ""
    signal_priority: int = 0

    allow_trade: bool = True
    allow_buy: bool = True
    allow_reduce: bool = True
    allow_sell: bool = True