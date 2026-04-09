from __future__ import annotations

import pandas as pd


# === 标准字段定义 ===
BAR_COLUMNS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


# === 常见字段映射（parquet / 不同来源用）===
COLUMN_ALIASES = {
    "timestamp": "date",
    "datetime": "date",
    "time": "date",

    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


def normalize_bar_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一字段名（比如 parquet 里的 Open -> open）
    """
    out = df.copy()
    rename_map = {
        col: COLUMN_ALIASES[col]
        for col in df.columns
        if col in COLUMN_ALIASES
    }
    return out.rename(columns=rename_map)


def validate_bar_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    校验 + 基础标准化
    """
    missing = set(BAR_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required bar columns: {sorted(missing)}")

    out = df.copy()

    # 时间列
    out["date"] = pd.to_datetime(out["date"])

    # 类型统一
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = out[col].astype(float)

    return out


def prepare_bar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    一步完成：normalize + validate
    （推荐统一入口）
    """
    out = normalize_bar_columns(df)
    out = validate_bar_schema(out)
    return out