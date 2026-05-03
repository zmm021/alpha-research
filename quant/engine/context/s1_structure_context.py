from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class S1StructureContext:
    """
    S1 Structure Context

    只承载结构信息，不做决策。

    slow:
        来自 Postgres daily structure。
        macro / sector / symbol 都有 slow。

    fast:
        来自 runtime 当前 symbol bar。
        当前阶段只有 symbol fast。

    设计原则：
        1. slow 定义背景结构
        2. fast 定义当前行为
        3. S1 不决定后续使用 slow 还是 fast
        4. S2/S3/S4/S5 自行选择 slow / fast
        5. 不在 S1 里做过多 shortcuts，避免隐藏信息来源
    """

    # ===== identity =====
    symbol: str = ""
    sector_name: str = ""
    timestamp: Any | None = None

    # ===== slow states（DB daily）=====
    slow_macro_state: str = ""
    slow_sector_state: str = ""
    slow_symbol_state: str = ""

    # ===== fast state（runtime symbol chain）=====
    symbol_state: str = ""

    # ===== slow variables（DB daily）=====
    macro_slow: dict[str, Any] = field(default_factory=dict)
    sector_slow: dict[str, Any] = field(default_factory=dict)
    symbol_slow: dict[str, Any] = field(default_factory=dict)

    # ===== fast variables（runtime）=====
    symbol_fast: dict[str, Any] = field(default_factory=dict)

    # ===== debug / trace =====
    slow_bundle: dict[str, Any] = field(default_factory=dict)
    symbol_snapshot: Any | None = None
    feature_row: dict[str, Any] | None = None

    # ===== helpers =====
    def get_macro_slow(self, key: str, default: Any = None) -> Any:
        return self.macro_slow.get(key, default)

    def get_sector_slow(self, key: str, default: Any = None) -> Any:
        return self.sector_slow.get(key, default)

    def get_symbol_slow(self, key: str, default: Any = None) -> Any:
        return self.symbol_slow.get(key, default)

    def get_symbol_fast(self, key: str, default: Any = None) -> Any:
        return self.symbol_fast.get(key, default)