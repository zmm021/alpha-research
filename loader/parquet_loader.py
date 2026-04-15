from __future__ import annotations

from pathlib import Path
import pandas as pd

from utils.bar_schema import prepare_bar_dataframe


def load_daily_parquet(
    base_path: Path,
    symbol: str,
    date: str,
) -> pd.DataFrame:
    """
    读取某一天 parquet
    """
    path = base_path / symbol / "historical" / date[:4] / date[:7] / f"{date}.parquet"

    df = pd.read_parquet(path)
    df = prepare_bar_dataframe(df)

    return df


def load_range(
    base_path: Path,
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    读取一段时间（拼接多个 parquet）
    """
    dates = pd.date_range(start_date, end_date, freq="B")

    dfs = []
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        try:
            df = load_daily_parquet(base_path, symbol, date_str)
            dfs.append(df)
        except FileNotFoundError:
            continue

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)