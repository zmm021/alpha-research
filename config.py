from pathlib import Path

# =========================
# 📁 Base Paths
# ========================= 

PROJECT_ROOT = Path(__file__).resolve().parent
BASE_DIR = PROJECT_ROOT / "data"
MARKET_DIR = BASE_DIR / "market" 

# symbol data structure
# Data/
#   market/
#       UUUU/
#           historical/
#           live/

def get_symbol_dir(symbol: str) -> Path:
    return MARKET_DIR / symbol

def get_historical_dir(symbol: str) -> Path:
    return get_symbol_dir(symbol) / "historical"

def get_live_dir(symbol: str) -> Path:
    return get_symbol_dir(symbol) / "live"


# =========================
# 📡 IBKR Connection
# =========================

IB_HOST = "127.0.0.1"
IB_PORT = 7496  # paper: 7497
IB_CLIENT_ID = 1


# =========================
# 📊 Symbols Config
# =========================

LIVE_SYMBOLS = [
    "UUUU",
    "CRML",
]

# =========================
# ⏱️ Live Data Config
# =========================

LIVE_POLL_SECONDS = 0.5
LIVE_FLUSH_EVERY = 20


# =========================
# 📦 File Format
# =========================

FILE_FORMAT = "parquet"  # or "csv"


# =========================
# 🧠 Indicator Config (L1)
# =========================

# 统一窗口参数（非常关键）
MA_WINDOWS = [5, 10, 20, 30, 50, 100, 200]
EMA_WINDOWS = [5, 12, 26, 50]

RSI_WINDOWS = [6, 14, 21]
ATR_WINDOWS = [14, 20]
STD_WINDOWS = [10, 20, 30]

ROLLING_HIGH_LOW_WINDOWS = [10, 20]

# =========================
# 🔥 Warm Start Config（关键）
# =========================

# online 启动时加载多少天数据
WARM_START_DAYS = 60

# 用于计算指标的最小数据量（防止指标不稳定）
MIN_HISTORY_REQUIRED = {
    "ma": 200,
    "ema": 50,
    "atr": 20,
    "rsi": 14,
}


# =========================
# 📊 Offline Snapshot Config
# =========================

SNAPSHOT_FREQUENCY = "daily"

# 是否保存 L1（可选优化）
STORE_L1_SNAPSHOT = False  # 推荐False，只存L2

# =========================
# 🚀 Feature Toggle（后面扩展用）
# =========================

ENABLE_L2 = True
ENABLE_L3 = False  # 先不做


# =========================
# 🧪 Debug / Dev
# =========================

DEBUG = True
LOG_LEVEL = "INFO"


# =========================
# 🧪 Postgres DB
# =========================
PG_HOST = "localhost"
PG_PORT = 5432
PG_DBNAME = "alpha_stack"
PG_USER = "trading_os"
PG_PASSWORD = "pwd_124"