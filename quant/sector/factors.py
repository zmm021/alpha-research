from __future__ import annotations

import pandas as pd

from quant.common.constants import Indicators, Factors, StructureScores
from quant.common.types import ConfigDict


def compute_sector_factors(ind_df: pd.DataFrame, config: ConfigDict) -> pd.DataFrame:

    cfg = config["factors"]

    out = pd.DataFrame(index=ind_df.index)

    rs = ind_df[Indicators.RS_Z]
    rs_mom = ind_df[Indicators.RS_MOMENTUM_Z]

    breadth = ind_df[Indicators.BREADTH_FRAC]
    breadth_mom = ind_df[Indicators.BREADTH_MOMENTUM]

    vol = ind_df[Indicators.VOL_RATIO_Z]
    vol_trend = ind_df[Indicators.VOL_TREND_Z]

    out[Factors.SECTOR_RELATIVE_STRENGTH_FACTOR] = cfg["rs_scale"] * rs

    out[Factors.SECTOR_BREADTH_FACTOR] = cfg["breadth_scale"] * breadth

    out[Factors.SECTOR_PARTICIPATION_FACTOR] = cfg["vol_scale"] * vol

    # 🔥 新增：结构动量
    out[Factors.SECTOR_MOMENTUM_FACTOR] = (
        cfg["rs_momentum_scale"] * rs_mom +
        cfg["breadth_momentum_scale"] * breadth_mom +
        cfg["vol_trend_scale"] * vol_trend
    )

    return out


def compute_sector_structure(fac_df: pd.DataFrame, config: ConfigDict) -> pd.DataFrame:

    cfg = config["structure"]

    out = pd.DataFrame(index=fac_df.index)

    rs = fac_df[Factors.SECTOR_RELATIVE_STRENGTH_FACTOR]
    breadth = fac_df[Factors.SECTOR_BREADTH_FACTOR]
    vol = fac_df[Factors.SECTOR_PARTICIPATION_FACTOR]
    momentum = fac_df[Factors.SECTOR_MOMENTUM_FACTOR]

    # 主结构评分
    out[StructureScores.SECTOR_SUPPORT_SCORE] = (
        cfg["rs_weight"] * rs +
        cfg["breadth_weight"] * breadth +
        cfg["vol_weight"] * vol
    )

    # 保留单独维度（避免信息压缩）
    out[StructureScores.SECTOR_BREADTH_HEALTH] = breadth
    out[StructureScores.SECTOR_MOMENTUM] = momentum

    return out