from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class S3SignalContext:
    """
    S3: Signal 层

    来源：
        SignalEngine

    职责：
        1. 输出当前交易信号（alpha_signal）
        2. 提供 gating（是否允许执行）
        3. 维护轻量 memory（cooldown / 去抖动）

    设计原则：
        - 不做 rolling，不需要 warmup
        - memory 仅用于稳定信号，不影响结构判断
    """

    # ===== 当前信号 =====
    alpha_signal: str = "hold"   # buy / sell / reduce / hold / avoid
    raw_signal: str = "hold"     # 未过滤的原始信号

    signal_reason: str = ""
    signal_priority: int = 0

    # ===== gating（来自 regime + signal 叠加）=====
    allow_trade: bool = False
    allow_buy: bool = False
    allow_reduce: bool = False
    allow_sell: bool = False

    # ===== memory（核心）=====
    last_emitted_signal: Optional[str] = None

    last_action_signal: Optional[str] = None
    last_action_time: Optional[Any] = None

    cooldown_active: bool = False

    # ===== debug / explain =====
    metadata: dict = field(default_factory=dict)