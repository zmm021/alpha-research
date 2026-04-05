from __future__ import annotations

from pathlib import Path
import argparse
import pandas as pd


def load_parquet(parquet_path: Path) -> pd.DataFrame:
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    df = pd.read_parquet(parquet_path)

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def filter_recent_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    max_dt = df["date"].max()
    cutoff = max_dt - pd.Timedelta(days=days)
    return df[df["date"] >= cutoff].copy()


def export_recent_csv(
    parquet_path: Path,
    output_csv: Path,
    days: int = 30,
) -> None:
    df = load_parquet(parquet_path)
    recent = filter_recent_days(df, days=days)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # 只保留展示链路需要的字段
    cols = ["date", "open", "high", "low", "close", "volume"]
    recent = recent[cols]

    # 输出成更通用的格式
    recent.to_csv(output_csv, index=False)

    print(f"Exported {len(recent)} rows to {output_csv}")
    print(f"Date range: {recent['date'].min()} -> {recent['date'].max()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export recent parquet market data to CSV")
    parser.add_argument("--symbol", required=True, help="e.g. UUUU")
    parser.add_argument("--input", required=True, help="Path to input parquet")
    parser.add_argument("--output", required=True, help="Path to output csv")
    parser.add_argument("--days", type=int, default=30, help="Recent days to keep")
    args = parser.parse_args()

    export_recent_csv(
        parquet_path=Path(args.input),
        output_csv=Path(args.output),
        days=args.days,
    )


if __name__ == "__main__":
    main()