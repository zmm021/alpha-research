from __future__ import annotations

import argparse

try:
    from .ib_data_store import pull_day, pull_month, pull_year
except ImportError:  # pragma: no cover
    from ingestion.ib_data_store import pull_day, pull_month, pull_year


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR batch historical data CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_year = subparsers.add_parser(
        "pull-year",
        help="Pull one full calendar year of 1-minute historical data",
    )
    parser_year.add_argument("--symbol", required=True, help="Stock symbol, e.g. UUUU")
    parser_year.add_argument("--year", required=True, type=int, help="Calendar year, e.g. 2015")
    parser_year.add_argument("--use-rth", action="store_true", help="Use regular trading hours only")

    parser_month = subparsers.add_parser(
        "pull-month",
        help="Pull one calendar month of 1-minute historical data",
    )
    parser_month.add_argument("--symbol", required=True, help="Stock symbol, e.g. UUUU")
    parser_month.add_argument("--month", required=True, help="Month in YYYY-MM format, e.g. 2025-01")
    parser_month.add_argument("--use-rth", action="store_true", help="Use regular trading hours only")

    parser_day = subparsers.add_parser(
        "pull-day",
        help="Pull one day of 1-minute historical data",
    )
    parser_day.add_argument("--symbol", required=True, help="Stock symbol, e.g. UUUU")
    parser_day.add_argument("--date", required=True, help="Date in YYYY-MM-DD format, e.g. 2025-01-01")
    parser_day.add_argument("--use-rth", action="store_true", help="Use regular trading hours only")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "pull-year":
        output = pull_year(symbol=args.symbol, year=args.year, use_rth=args.use_rth)
    elif args.command == "pull-month":
        output = pull_month(symbol=args.symbol, month=args.month, use_rth=args.use_rth)
    elif args.command == "pull-day":
        output = pull_day(symbol=args.symbol, target_date=args.date, use_rth=args.use_rth)
    else:  # pragma: no cover
        raise ValueError(f"Unsupported command: {args.command}")

    print(f"[DONE] Historical data saved to: {output}")


if __name__ == "__main__":
    main()
