from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import FILE_FORMAT, IB_CLIENT_ID, IB_HOST, IB_PORT

try:
    from .ib_data_lib import (
        connect_ib,
        store_day_history,
        store_month_history,
        store_year_history,
    )
except ImportError:  # pragma: no cover
    from ingestion.ib_data_lib import (
        connect_ib,
        store_day_history,
        store_month_history,
        store_year_history,
    )


def pull_year(symbol: str, year: int, use_rth: bool = True) -> Path:
    ib = connect_ib(host=IB_HOST, port=IB_PORT, client_id=IB_CLIENT_ID)
    try:
        return store_year_history(
            ib=ib,
            symbol=symbol,
            year=year,
            use_rth=use_rth,
            file_format=FILE_FORMAT,
            replace_existing=True,
        )
    finally:
        ib.disconnect()


def pull_month(symbol: str, month: str, use_rth: bool = True) -> Path:
    parsed = datetime.strptime(month, "%Y-%m")
    ib = connect_ib(host=IB_HOST, port=IB_PORT, client_id=IB_CLIENT_ID)
    try:
        return store_month_history(
            ib=ib,
            symbol=symbol,
            year=parsed.year,
            month=parsed.month,
            use_rth=use_rth,
            file_format=FILE_FORMAT,
            replace_existing=True,
        )
    finally:
        ib.disconnect()


def pull_day(symbol: str, target_date: str, use_rth: bool = True) -> Path:
    parsed = datetime.strptime(target_date, "%Y-%m-%d").date()
    ib = connect_ib(host=IB_HOST, port=IB_PORT, client_id=IB_CLIENT_ID)
    try:
        return store_day_history(
            ib=ib,
            symbol=symbol,
            target_date=parsed,
            use_rth=use_rth,
            file_format=FILE_FORMAT,
            replace_existing=True,
        )
    finally:
        ib.disconnect()
