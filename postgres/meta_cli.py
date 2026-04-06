from __future__ import annotations

import argparse
import json

from postgres.meta_repo import (
    get_all_sectors,
    get_related_symbols,
    get_sector_symbols,
    get_sector_symbols_with_meta,
    get_symbol_sectors,
    get_macro_groups,
    get_macro_symbols,
    get_macro_symbols_by_group,
    get_macro_symbols_with_meta,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Postgres metadata CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p1 = subparsers.add_parser(
        "get-sector-symbols",
        help="Get symbols for a sector",
    )
    p1.add_argument("--sector", required=True, help="Sector name, e.g. uranium")
    p1.add_argument(
        "--asset-type",
        required=False,
        help="Optional asset type filter, e.g. stock / etf",
    )

    p2 = subparsers.add_parser(
        "get-sector-symbols-meta",
        help="Get symbols with metadata for a sector",
    )
    p2.add_argument("--sector", required=True, help="Sector name, e.g. rare_earth")

    p3 = subparsers.add_parser(
        "get-sectors",
        help="Get all sectors",
    )

    p4 = subparsers.add_parser(
        "get-related-symbols",
        help="Get related symbols through shared sectors",
    )
    p4.add_argument("--symbol", required=True, help="Symbol, e.g. UUUU")
    p4.add_argument("--sector", required=False, help="Optional sector filter, e.g. uranium")

    p5 = subparsers.add_parser(
        "get-symbol-sectors",
        help="Get all sectors for a symbol",
    )
    p5.add_argument("--symbol", required=True, help="Symbol, e.g. UUUU")
    p6 = subparsers.add_parser(
        "get-macro-symbols",
        help="Get all macro symbols"
    )

    p7 = subparsers.add_parser(
        "get-macro-by-group",
        help="Get macro symbols by group"
    )
    p7.add_argument("--group", required=True)
    p8 = subparsers.add_parser(
        "get-macro-groups",
        help="Get all macro groups"
    )
    p9 = subparsers.add_parser(
        "get-macro-symbols-meta",
        help="Get macro symbols with metadata"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "get-sector-symbols":
        result = get_sector_symbols(
            sector_name=args.sector,
            asset_type=args.asset_type,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, default=float))

    elif args.command == "get-sector-symbols-meta":
        result = get_sector_symbols_with_meta(args.sector)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=float))

    elif args.command == "get-sectors":
        result = get_all_sectors()
        print(json.dumps(result, indent=2, ensure_ascii=False, default=float))

    elif args.command == "get-related-symbols":
        result = get_related_symbols(args.symbol, args.sector)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "get-symbol-sectors":
        result = get_symbol_sectors(args.symbol)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    elif args.command == "get-macro-symbols":
        result = get_macro_symbols()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "get-macro-by-group":
        result = get_macro_symbols_by_group(args.group)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "get-macro-groups":
        result = get_macro_groups()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "get-macro-symbols-meta":
        result = get_macro_symbols_with_meta()
        print(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()