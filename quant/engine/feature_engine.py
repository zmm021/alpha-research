from __future__ import annotations

import pandas as pd

from quant.symbol.indicators import compute_symbol_indicators
from quant.symbol.factors import compute_symbol_factors, compute_symbol_contexts
from quant.symbol.state import compute_symbol_states

from quant.sector.indicators import compute_sector_indicators
from quant.sector.factors import compute_sector_factors, compute_sector_contexts
from quant.sector.state import compute_sector_states

from quant.macro.indicators import compute_macro_indicators
from quant.macro.factors import compute_macro_factors, compute_macro_contexts
from quant.macro.state import compute_macro_states


SECTOR_SUFFIX = "_sector"
MACRO_SUFFIX = "_macro"


# =========================
# Helpers
# =========================

def _ensure_sorted_index(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"{name} must have DatetimeIndex")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    return df


def _validate_required_df(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df is None:
        raise ValueError(f"{name} is None")

    if df.empty:
        raise ValueError(f"{name} is empty")

    return _ensure_sorted_index(df, name)


def _validate_member_dfs(member_dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if member_dfs is None:
        raise ValueError("sector_member_dfs is None")

    if not isinstance(member_dfs, dict):
        raise ValueError("sector_member_dfs must be a dict[str, pd.DataFrame]")

    if len(member_dfs) == 0:
        raise ValueError("sector_member_dfs is empty")

    validated: dict[str, pd.DataFrame] = {}

    for symbol, df in member_dfs.items():
        if df is None:
            raise ValueError(f"sector_member_dfs[{symbol}] is None")

        if df.empty:
            raise ValueError(f"sector_member_dfs[{symbol}] is empty")

        validated[symbol] = _ensure_sorted_index(df, f"sector_member_dfs[{symbol}]")

    return validated


def _validate_config_bundle(config_bundle: dict) -> None:
    if config_bundle is None:
        raise ValueError("config_bundle is None")

    required_keys = ["symbol", "sector", "macro"]
    missing = [k for k in required_keys if k not in config_bundle]
    if missing:
        raise ValueError(f"config_bundle missing required keys: {missing}")


def _align_to_symbol_index(
    symbol_index: pd.Index,
    df: pd.DataFrame,
    name: str,
) -> pd.DataFrame:
    """
    Align external dataframe (macro/sector) to symbol timeline.
    Uses forward fill ONLY to avoid lookahead bias.
    """
    if df is None:
        raise ValueError(f"{name} is None")

    if df.empty:
        raise ValueError(f"{name} dataframe is empty")

    df = _ensure_sorted_index(df, name)

    aligned = df.reindex(symbol_index, method="ffill")

    return aligned


def _safe_join(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """
    Join with explicit protection:
    - prevent silent overwrite
    - enforce column uniqueness
    """
    overlap = set(base.columns).intersection(set(other.columns))
    if overlap:
        raise ValueError(f"Column overlap detected: {sorted(overlap)}")

    return base.join(other)


# =========================
# Core Engine
# =========================

def build_feature_frame(
    symbol_df: pd.DataFrame,
    sector_etf_df: pd.DataFrame,
    sector_member_dfs: dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    hy_oas_df: pd.DataFrame,
    config_bundle: dict,
) -> pd.DataFrame:
    """
    Build unified feature frame.

    Output:
        index = symbol timeline
        columns =
            symbol indicators / factors / contexts / state
            sector indicators / factors / contexts / state (aligned, suffixed)
            macro indicators / factors / contexts / state (aligned, suffixed)
    """

    # =========================
    # Validate Inputs
    # =========================
    _validate_config_bundle(config_bundle)

    symbol_df = _validate_required_df(symbol_df, "symbol_df")
    sector_etf_df = _validate_required_df(sector_etf_df, "sector_etf_df")
    spy_df = _validate_required_df(spy_df, "spy_df")
    vix_df = _validate_required_df(vix_df, "vix_df")
    hy_oas_df = _validate_required_df(hy_oas_df, "hy_oas_df")
    sector_member_dfs = _validate_member_dfs(sector_member_dfs)

    symbol_config = config_bundle["symbol"]
    sector_config = config_bundle["sector"]
    macro_config = config_bundle["macro"]

    # =========================
    # SYMBOL LAYER
    # =========================
    symbol_ind = compute_symbol_indicators(symbol_df, symbol_config)
    symbol_fac = compute_symbol_factors(symbol_ind, symbol_config)
    symbol_ctx = compute_symbol_contexts(symbol_fac, symbol_config)
    symbol_state = compute_symbol_states(symbol_ctx, symbol_config)

    symbol_full = symbol_ind.join(symbol_fac).join(symbol_ctx)
    symbol_full["symbol_state"] = symbol_state
    symbol_full = symbol_full.copy()

    # =========================
    # SECTOR LAYER
    # =========================
    sector_ind = compute_sector_indicators(
        sector_etf_df=sector_etf_df,
        member_dfs=sector_member_dfs,
        spy_df=spy_df,
        config=sector_config,
    )
    sector_fac = compute_sector_factors(sector_ind, sector_config)
    sector_ctx = compute_sector_contexts(sector_fac, sector_config)
    sector_state = compute_sector_states(sector_ctx, sector_config)

    sector_full = sector_ind.join(sector_fac).join(sector_ctx)
    sector_full["sector_state"] = sector_state

    # =========================
    # MACRO LAYER
    # =========================
    macro_ind = compute_macro_indicators(
        spy_df=spy_df,
        vix_df=vix_df,
        hy_oas_df=hy_oas_df,
        config=macro_config,
    )
    macro_fac = compute_macro_factors(macro_ind, macro_config)
    macro_ctx = compute_macro_contexts(macro_fac, macro_config)
    macro_state = compute_macro_states(macro_ctx, macro_config)

    macro_full = macro_ind.join(macro_fac).join(macro_ctx)
    macro_full["macro_state"] = macro_state

    # =========================
    # ALIGNMENT
    # =========================
    symbol_index = symbol_df.index

    sector_aligned = _align_to_symbol_index(symbol_index, sector_full, "sector_full")
    macro_aligned = _align_to_symbol_index(symbol_index, macro_full, "macro_full")

    sector_aligned = sector_aligned.add_suffix(SECTOR_SUFFIX)
    macro_aligned = macro_aligned.add_suffix(MACRO_SUFFIX)

    # =========================
    # MERGE
    # =========================
    final_df = _safe_join(symbol_full, sector_aligned)
    final_df = _safe_join(final_df, macro_aligned)

    # =========================
    # FINAL CLEANUP
    # =========================
    final_df = final_df.sort_index()

    return final_df