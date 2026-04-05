from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

from config import BASE_DIR


def load_history(symbol: str) -> pd.DataFrame:
    path = BASE_DIR / symbol.upper() / "historical" / f"{symbol.upper()}_year.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Historical file not found: {path}")

    df = pd.read_parquet(path)

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"]).set_index("date")

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    return df


def resample_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    interval_map = {
        "1min": "1min",
        "5min": "5min",
        "15min": "15min",
        "30min": "30min",
        "1h": "1h",
        "4h": "4h",
        "1D": "1D",
    }

    if interval not in interval_map:
        raise ValueError(f"Unsupported interval: {interval}")

    rule = interval_map[interval]

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    out = df.resample(rule).agg(agg).dropna(subset=["open", "high", "low", "close"])
    return out


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.astype(float)


def plot_chart(symbol: str, interval: str, last_n: int | None = None, save_path: str | None = None) -> None:
    raw = load_history(symbol)
    df = resample_ohlcv(raw, interval)

    print(f"Loaded raw rows: {len(raw)}")
    print(f"Resampled rows: {len(df)}")
    print(df.tail(5)[['open', 'high', 'low', 'close', 'volume']])

    if last_n is not None:
        df = df.tail(last_n)

    if df.empty:
        raise ValueError("No data to plot after resampling/filtering.")

    df = df.copy()
    df["rsi14"] = calc_rsi(df["close"], 14)

    addplots = [
        mpf.make_addplot(df["rsi14"], panel=2, ylabel="RSI(14)")
    ]

    plot_df = df.rename(columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })

    fig, _ = mpf.plot(
        plot_df,
        type="candle",
        style="yahoo",
        volume=True,
        addplot=addplots,
        title=f"{symbol.upper()} - {interval}",
        figsize=(16, 9),
        panel_ratios=(6, 2, 2),
        mav=(20, 50),
        tight_layout=True,
        show_nontrading=False,
        returnfig=True,
    )

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved chart to: {save_path}")

    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot historical OHLCV chart from parquet")
    parser.add_argument("--symbol", required=True, help="e.g. UUUU")
    parser.add_argument("--interval", default="1h", help="1min, 5min, 15min, 30min, 1h, 4h, 1D")
    parser.add_argument("--last-n", type=int, default=300, help="Only plot last N bars")
    parser.add_argument("--save", default=None, help="Optional output image path, e.g. uuuu_1h.png")
    args = parser.parse_args()

    plot_chart(
        symbol=args.symbol,
        interval=args.interval,
        last_n=args.last_n,
        save_path=args.save,
    )


if __name__ == "__main__":
    main()
    print("POC_CHART_STARTED")