#输入：
#  sector = uranium
#流程：
#  1. 拿到 sector 下所有 symbols
#  2. 查每个 symbol 的 offset
#  3. 计算 start_date（offset + 1 business day）
#  4. end_date = 昨天
#  5. 调 source 拉数据
#  6. 成功后 update offset = end_date
from __future__ import annotations

from datetime import datetime, timedelta, date

from source.ib_data_store import pull_day
from postgres import meta_repo


DEFAULT_START_DATE = "2025-01-01"
DEFAULT_SECTOR = "uranium"

def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def is_business_day(d: date) -> bool:
    return d.weekday() < 5  # Mon-Fri


def next_business_day(d: date) -> date:
    current = d + timedelta(days=1)
    while not is_business_day(current):
        current += timedelta(days=1)
    return current


def get_yesterday_business_day() -> date:
    current = date.today() - timedelta(days=1)
    while not is_business_day(current):
        current -= timedelta(days=1)
    return current


def business_days_between(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        if is_business_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


def get_symbol_start_date(symbol: str) -> date:
    last_offset = meta_repo.get_last_offset(symbol)

    if last_offset is None:
        return parse_date(DEFAULT_START_DATE)

    return next_business_day(parse_date(last_offset))


def pull_symbol_incremental(symbol: str, end_date: date) -> bool:
    start_date = get_symbol_start_date(symbol)

    if start_date > end_date:
        print(f"[SKIP] {symbol}: already up to date")
        return True

    target_days = business_days_between(start_date, end_date)

    if not target_days:
        print(f"[SKIP] {symbol}: no business days to pull")
        return True

    print(
        f"[INFO] Pulling {symbol} from {format_date(start_date)} "
        f"to {format_date(end_date)} ({len(target_days)} business days)"
    )

    for d in target_days:
        day_str = format_date(d)
        try:
            pull_day(symbol=symbol, target_date=day_str, use_rth=True)
            print(f"[OK] Pulled {symbol} {day_str}")
        except Exception as e:
            print(f"[ERROR] Failed pulling {symbol} {day_str}: {e}")
            return False

    meta_repo.update_offset(symbol, format_date(end_date))
    print(f"[OK] Updated offset for {symbol} -> {format_date(end_date)}")
    return True


def run_sector_pipeline(sector: str = DEFAULT_SECTOR) -> None:
    symbols = meta_repo.get_sector_symbols(sector_name=sector, asset_type="stock")
    end_date = get_yesterday_business_day()

    print(f"[INFO] Sector: {sector}")
    print(f"[INFO] End date: {format_date(end_date)}")
    print(f"[INFO] Symbols: {symbols}")

    for symbol in symbols:
        print(f"\n=== Processing {symbol} ===")
        success = pull_symbol_incremental(symbol, end_date)
        if not success:
            print(f"[WARN] Stop updating offset for {symbol} due to failure")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sector", default=DEFAULT_SECTOR)
    args = parser.parse_args()

    run_sector_pipeline(args.sector)