from __future__ import annotations

from quant.indicators import MarketState


# =========
# Raw cols
# =========
COL_DATE = "date"
COL_OPEN = "open"
COL_HIGH = "high"
COL_LOW = "low"
COL_CLOSE = "close"
COL_VOLUME = "volume"

COL_SPY_RETURN = "spy_return"
COL_QQQ_RETURN = "qqq_return"
COL_SECTOR_RETURN = "sector_return"


# ==================
# State value names
# ==================
STATE_BULLISH = MarketState.BULLISH.value
STATE_BEARISH = MarketState.BEARISH.value
STATE_NEUTRAL = MarketState.NEUTRAL.value
STATE_OVERBOUGHT = MarketState.OVERBOUGHT.value
STATE_OVERSOLD = MarketState.OVERSOLD.value
STATE_GOLDEN_CROSS = MarketState.GOLDEN_CROSS.value
STATE_DEATH_CROSS = MarketState.DEATH_CROSS.value
STATE_NONE = MarketState.NONE.value


# =================
# Column name utils
# =================
def ma_col(window: int) -> str:
    return f"ma_{window}"


def ema_col(window: int) -> str:
    return f"ema_{window}"


def rsi_col(window: int) -> str:
    return f"rsi_{window}"


def atr_col(window: int) -> str:
    return f"atr_{window}"


def rolling_std_col(window: int) -> str:
    return f"rolling_std_{window}"


def highest_high_col(window: int) -> str:
    return f"highest_high_{window}"


def lowest_low_col(window: int) -> str:
    return f"lowest_low_{window}"


def return_col(window: int) -> str:
    return f"return_{window}d"


def avg_volume_col(window: int) -> str:
    return f"avg_volume_{window}"


# ============
# Fixed L1 cols
# ============
COL_MACD_DIFF = "macd_diff"
COL_MACD_DEA = "macd_dea"
COL_MACD_HIST = "macd_hist"

COL_BOLL_MID = "boll_mid"
COL_BOLL_UPPER = "boll_upper"
COL_BOLL_LOWER = "boll_lower"
COL_BOLL_WIDTH = "boll_width"

COL_HL_RANGE = "hl_range"
COL_OC_CHANGE = "oc_change"
COL_LOG_RETURN_1D = "log_return_1d"


# ============
# Fixed L2 cols
# ============
COL_PRICE_VS_MA20 = "price_vs_ma20"
COL_PRICE_VS_MA50 = "price_vs_ma50"
COL_PRICE_VS_MA200 = "price_vs_ma200"

COL_MA20_SLOPE = "ma20_slope"
COL_MA50_SLOPE = "ma50_slope"
COL_MA200_SLOPE = "ma200_slope"

COL_MA_ALIGNMENT_BULLISH = "ma_alignment_bullish"
COL_MA_ALIGNMENT_BEARISH = "ma_alignment_bearish"
COL_TREND_STRENGTH = "trend_strength"

COL_RSI_STATE = "rsi_state"
COL_RSI_REGIME = "rsi_regime"

COL_MACD_CROSS_STATE = "macd_cross_state"
COL_MACD_TREND_STATE = "macd_trend_state"

COL_ATR_PCT = "atr_pct"
COL_VOL_PERCENTILE_20 = "vol_percentile_20"
COL_ATR_PERCENTILE_60 = "atr_percentile_60"

COL_BOLL_POSITION = "boll_position"
COL_PRICE_VS_BOLL_MID = "price_vs_boll_mid"
COL_BOLL_WIDTH_PCT = "boll_width_pct"

COL_DISTANCE_TO_RECENT_HIGH = "distance_to_recent_high"
COL_DISTANCE_TO_RECENT_LOW = "distance_to_recent_low"

COL_RANGE_EFFICIENCY = "range_efficiency"
COL_CHOPINESS_INDEX = "chopiness_index"

COL_DRAWDOWN_FROM_PEAK = "drawdown_from_peak"
COL_REBOUND_FROM_LOW = "rebound_from_low"

COL_VOLUME_VS_AVG20 = "volume_vs_avg20"
COL_LIQUIDITY_SCORE = "liquidity_score"

COL_SYMBOL_VS_MARKET = "symbol_vs_market"
COL_SECTOR_STRENGTH = "sector_strength"