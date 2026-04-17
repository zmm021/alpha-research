"""
Shared names/constants for Alpha Stack quant modules.

Principles:
- Only keep phase-1 core names here.
- Use stable snake_case strings.
- Separate raw indicators, factors, contexts, and common fields.
"""


class Fields:
    TIMESTAMP = "timestamp"
    SYMBOL = "symbol"

    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"


class Indicators:
    # ===== Macro =====
    SPY_TREND_Z = "spy_trend_z"
    VIX_Z = "vix_z"
    HY_OAS_Z = "hy_oas_z"

    # ===== Sector =====
    RS_Z = "rs_z"
    BREADTH_FRAC = "breadth_frac"
    VOL_RATIO_Z = "vol_ratio_z"
    BREADTH_MOMENTUM = "breadth_momentum"
    # ===== Symbol =====
    MA20 = "ma20"
    MA50 = "ma50"
    MA20_SLOPE = "ma20_slope"

    ATR_PCT = "atr_pct"

    DISTANCE_TO_HIGH = "distance_to_high"
    VOLUME_RATIO = "volume_ratio"

    GAP_PCT = "gap_pct"
    PRICE_VS_VWAP = "price_vs_vwap"
    RS_MOMENTUM_Z = "rs_momentum_z"
    VOL_TREND_Z = "vol_trend_z"

class Factors:
    # ===== Macro factors =====
    MACRO_TREND_FACTOR = "macro_trend_factor"
    MACRO_VOLATILITY_FACTOR = "macro_volatility_factor"
    MACRO_CREDIT_RISK_FACTOR = "macro_credit_risk_factor"

    # ===== Sector factors =====
    SECTOR_RELATIVE_STRENGTH_FACTOR = "sector_relative_strength_factor"
    SECTOR_BREADTH_FACTOR = "sector_breadth_factor"
    SECTOR_PARTICIPATION_FACTOR = "sector_participation_factor"
    SECTOR_MOMENTUM_FACTOR = "sector_momentun_factor"
    # ===== Symbol factors =====
    SYMBOL_TREND_FACTOR = "symbol_trend_factor"
    SYMBOL_TREND_SLOPE_FACTOR = "symbol_trend_slope_factor"
    SYMBOL_VOLATILITY_FACTOR = "symbol_volatility_factor"
    SYMBOL_LIQUIDITY_FACTOR = "symbol_liquidity_factor"
    SYMBOL_POSITION_FACTOR = "symbol_position_factor"
    SYMBOL_INTRADAY_INTENT_FACTOR = "symbol_intraday_intent_factor"


class Contexts:
    # ===== Macro contexts =====
    MACRO_TREND_STRENGTH = "macro_trend_strength"
    MACRO_RISK_PRESSURE = "macro_risk_pressure"

    # ===== Sector contexts =====
    SECTOR_SUPPORT_SCORE = "sector_support_score"
    SECTOR_BREADTH_HEALTH = "sector_breadth_health"
    SECTOR_MOMENTUM = "sector_momentum"
    # ===== Symbol contexts =====
    SYMBOL_TREND_STRENGTH = "symbol_trend_strength"
    SYMBOL_TREND_SLOPE = "symbol_trend_slope"
    SYMBOL_REVERSAL_PRESSURE = "symbol_reversal_pressure"
    SYMBOL_VOLATILITY_STATE = "symbol_volatility_state"
    SYMBOL_POSITION_QUALITY = "symbol_position_quality"
    SYMBOL_INTRADAY_INTENT = "symbol_intraday_intent"
    SYMBOL_EXHAUSTION_RISK = "symbol_exhaustion_risk"
    SYMBOL_FAILURE_RISK = "symbol_failure_risk"
    SYMBOL_LIQUIDITY_QUALITY = "symbol_liquidity_quality"