from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from postgres import meta_repo
from source.ib_data_store import pull_days


DEFAULT_START_DATE = "2025-01-01"


def is_business_day(d: date) -> bool:
    return d.weekday() < 5


def previous_business_day(d: date) -> date:
    d = d - timedelta(days=1)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def next_business_day(d: date) -> date:
    d = d + timedelta(days=1)
    while not is_business_day(d):
        d += timedelta(days=1)
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


def resolve_offset_start(symbol: str) -> date:
    offset = meta_repo.get_offset(symbol)

    if offset is None:
        return datetime.strptime(DEFAULT_START_DATE, "%Y-%m-%d").date()

    if isinstance(offset, str):
        offset_date = datetime.strptime(offset, "%Y-%m-%d").date()
    else:
        offset_date = offset

    return next_business_day(offset_date)


def run_incremental_ingestion(
    *,
    sector: str | None,
    macro: bool,
    symbol: str | None,
) -> None:
    source_label, symbols = resolve_symbols(
        sector=sector,
        macro=macro,
        symbol=symbol,
    )

    today = date.today()
    end_date = previous_business_day(today)

    print(f"[INFO] Running incremental ingestion for {source_label}")
    print(f"[INFO] Symbols: {symbols}")
    print(f"[INFO] Target end date: {end_date}")

    for sym in symbols:
        try:
            start_date = resolve_offset_start(sym)

            if start_date > end_date:
                print(f"[INFO] Skip {sym}: no new business day to pull")
                continue

            print(f"\n=== Incremental pull | {sym} | {start_date} -> {end_date} ===")

            pull_days(
                symbol=sym,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                use_rth=True,
            )

            meta_repo.update_offset(sym, end_date.strftime("%Y-%m-%d"))
            print(f"[OK] Updated offset for {sym} -> {end_date}")

        except Exception as e:
            print(f"[ERROR] Failed incremental ingestion for {sym}: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incremental ingestion pipeline")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sector", help="Sector name, e.g. uranium")
    group.add_argument("--macro", "--marco", action="store_true", help="Run for macro symbols")
    group.add_argument("--symbol", help="Single symbol, e.g. UUUU")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    run_incremental_ingestion(
        sector=getattr(args, "sector", None),
        macro=getattr(args, "macro", False),
        symbol=getattr(args, "symbol", None),
    )


if __name__ == "__main__":
    main()