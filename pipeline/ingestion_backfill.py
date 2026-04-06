from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta

from postgres import meta_repo
from source.ib_data_store import pull_month, pull_year


def parse_month(month_str: str) -> tuple[int, int]:
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.year, dt.month


def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def last_business_day_of_year(year: int) -> date:
    d = date(year, 12, 31)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def last_business_day_of_month(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def run_backfill_year(sector: str, year: int) -> None:
    symbols = meta_repo.get_sector_symbols(sector_name=sector, asset_type="stock")
    target_offset = last_business_day_of_year(year).strftime("%Y-%m-%d")

    print(f"[INFO] Backfill year {year} for sector={sector}")
    print(f"[INFO] Symbols: {symbols}")
    print(f"[INFO] Target offset: {target_offset}")

    for symbol in symbols:
        print(f"\n=== Backfill year {year} | {symbol} ===")
        try:
            pull_year(symbol=symbol, year=year, use_rth=True)
            meta_repo.update_offset(symbol, target_offset)
            print(f"[OK] Updated offset for {symbol} -> {target_offset}")
        except Exception as e:
            print(f"[ERROR] Failed year backfill for {symbol}: {e}")


def run_backfill_month(sector: str, month_str: str) -> None:
    year, month = parse_month(month_str)
    symbols = meta_repo.get_sector_symbols(sector_name=sector, asset_type="stock")
    target_offset = last_business_day_of_month(year, month).strftime("%Y-%m-%d")

    print(f"[INFO] Backfill month {month_str} for sector={sector}")
    print(f"[INFO] Symbols: {symbols}")
    print(f"[INFO] Target offset: {target_offset}")

    for symbol in symbols:
        print(f"\n=== Backfill month {month_str} | {symbol} ===")
        try:
            pull_month(symbol=symbol, month=month_str, use_rth=True)
            meta_repo.update_offset(symbol, target_offset)
            print(f"[OK] Updated offset for {symbol} -> {target_offset}")
        except Exception as e:
            print(f"[ERROR] Failed month backfill for {symbol}: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sector backfill pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p1 = subparsers.add_parser("backfill-year", help="Backfill one full year for a sector")
    p1.add_argument("--sector", required=True)
    p1.add_argument("--year", required=True, type=int)

    p2 = subparsers.add_parser("backfill-month", help="Backfill one month for a sector")
    p2.add_argument("--sector", required=True)
    p2.add_argument("--month", required=True, help="YYYY-MM")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "backfill-year":
        run_backfill_year(args.sector, args.year)
    elif args.command == "backfill-month":
        run_backfill_month(args.sector, args.month)
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()