from __future__ import annotations

import pandas as pd

from quant.common.constants import StructureScores
from quant.common.enums import SectorState
from quant.common.schemas import StructureOutput
from quant.common.types import ConfigDict


def _compute_single_sector_state(
    support_score: float,
    breadth_health: float,
    config: ConfigDict,
) -> SectorState:
    """
    Phase-1 sector state logic:

    - LEADING: support strong + breadth healthy
    - WEAK: support weak or breadth weak
    - otherwise MIXED
    """
    state_cfg = config["state"]

    # 保留 fallback，增强工程安全
    leading_threshold = float(state_cfg.get("leading_threshold", 0.5))
    weak_threshold = float(state_cfg.get("weak_threshold", -0.2))
    breadth_strong_threshold = float(state_cfg.get("breadth_strong_threshold", 0.55))
    breadth_weak_threshold = float(state_cfg.get("breadth_weak_threshold", 0.45))

    if support_score >= leading_threshold and breadth_health >= breadth_strong_threshold:
        return SectorState.LEADING

    if support_score <= weak_threshold or breadth_health <= breadth_weak_threshold:
        return SectorState.WEAK

    return SectorState.MIXED


def compute_sector_states(
    context_df: pd.DataFrame,
    config: ConfigDict,
) -> pd.Series:
    """
    Compute sector state series from sector StructureScrores.
    """
    required_cols = [
        StructureScores.SECTOR_SUPPORT_SCORE,
        StructureScores.SECTOR_BREADTH_HEALTH,
    ]
    missing = [c for c in required_cols if c not in context_df.columns]
    if missing:
        raise ValueError(f"Missing required structure score columns for sector state: {missing}")

    return context_df.apply(
        lambda row: _compute_single_sector_state(
            support_score=float(row[StructureScores.SECTOR_SUPPORT_SCORE]),
            breadth_health=float(row[StructureScores.SECTOR_BREADTH_HEALTH]),
            config=config,
        ),
        axis=1,
    )


def compute_sector_state_output(
    structure_output: StructureOutput,
    config: ConfigDict,
) -> SectorState:
    """
    Convenience helper for latest-row / snapshot use cases.
    """
    values = structure_output.values

    return _compute_single_sector_state(
        support_score=float(values.get(StructureScores.SECTOR_SUPPORT_SCORE, 0.0)),
        breadth_health=float(values.get(StructureScores.SECTOR_BREADTH_HEALTH, 0.0)),
        config=config,
    )