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


def resolve_symbols(
    *,
    sector: str | None,
    macro: bool,
    symbol: str | None,
) -> tuple[str, list[str]]:
    chosen = sum([bool(sector), bool(macro), bool(symbol)])
    if chosen != 1:
        raise ValueError("Provide exactly one of: --sector, --macro/--marco, --symbol")

    if symbol:
        return f"symbol={symbol}", [symbol.upper()]

    if macro:
        symbols = meta_repo.get_macro_symbols()
        if not symbols:
            raise ValueError("No macro symbols found")
        return "macro", symbols

    symbols = meta_repo.get_sector_symbols(sector_name=sector, asset_type="stock")
    if not symbols:
        raise ValueError(f"No sector symbols found for sector={sector}")
    return f"sector={sector}", symbols


def run_backfill_year(
    *,
    sector: str | None,
    macro: bool,
    symbol: str | None,
    year: int,
) -> None:
    source_label, symbols = resolve_symbols(
        sector=sector,
        macro=macro,
        symbol=symbol,
    )
    target_offset = last_business_day_of_year(year).strftime("%Y-%m-%d")

    print(f"[INFO] Backfill year {year} for {source_label}")
    print(f"[INFO] Symbols: {symbols}")
    print(f"[INFO] Target offset: {target_offset}")

    for sym in symbols:
        print(f"\n=== Backfill year {year} | {sym} ===")
        try:
            pull_year(symbol=sym, year=year, use_rth=True)
            meta_repo.update_offset(sym, target_offset)
            print(f"[OK] Updated offset for {sym} -> {target_offset}")
        except Exception as e:
            print(f"[ERROR] Failed year backfill for {sym}: {e}")


def run_backfill_month(
    *,
    sector: str | None,
    macro: bool,
    symbol: str | None,
    month_str: str,
) -> None:
    year, month = parse_month(month_str)
    source_label, symbols = resolve_symbols(
        sector=sector,
        macro=macro,
        symbol=symbol,
    )
    target_offset = last_business_day_of_month(year, month).strftime("%Y-%m-%d")

    print(f"[INFO] Backfill month {month_str} for {source_label}")
    print(f"[INFO] Symbols: {symbols}")
    print(f"[INFO] Target offset: {target_offset}")

    for sym in symbols:
        print(f"\n=== Backfill month {month_str} | {sym} ===")
        try:
            pull_month(symbol=sym, month=month_str, use_rth=True)
            meta_repo.update_offset(sym, target_offset)
            print(f"[OK] Updated offset for {sym} -> {target_offset}")
        except Exception as e:
            print(f"[ERROR] Failed month backfill for {sym}: {e}")


def add_source_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sector", help="Sector name, e.g. uranium")
    group.add_argument("--macro", "--marco", action="store_true", help="Backfill all macro symbols")
    group.add_argument("--symbol", help="Single symbol, e.g. UUUU")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p1 = subparsers.add_parser("backfill-year", help="Backfill one full year")
    add_source_args(p1)
    p1.add_argument("--year", required=True, type=int)

    p2 = subparsers.add_parser("backfill-month", help="Backfill one month")
    add_source_args(p2)
    p2.add_argument("--month", required=True, help="YYYY-MM")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "backfill-year":
        run_backfill_year(
            sector=getattr(args, "sector", None),
            macro=getattr(args, "macro", False),
            symbol=getattr(args, "symbol", None),
            year=args.year,
        )
    elif args.command == "backfill-month":
        run_backfill_month(
            sector=getattr(args, "sector", None),
            macro=getattr(args, "macro", False),
            symbol=getattr(args, "symbol", None),
            month_str=args.month,
        )
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()