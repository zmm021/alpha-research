from __future__ import annotations

from datetime import date
from typing import Any

from postgres.pg_client import fetch_all, fetch_one, execute


# =========================================================
# Helpers
# =========================================================

def _to_date_str(d: date | str) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if v is not None}


def _build_upsert_sql(
    *,
    table: str,
    row: dict[str, Any],
    conflict_cols: list[str],
) -> tuple[str, list[Any]]:
    row = _clean_row(row)

    cols = list(row.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)

    update_cols = [c for c in cols if c not in conflict_cols]
    update_sql = ", ".join(
        [f"{c} = EXCLUDED.{c}" for c in update_cols]
        + ["updated_at = CURRENT_TIMESTAMP"]
    )

    conflict_sql = ", ".join(conflict_cols)

    sql = f"""
    INSERT INTO public.{table} ({col_sql})
    VALUES ({placeholders})
    ON CONFLICT ({conflict_sql})
    DO UPDATE SET
        {update_sql}
    """

    return sql, [row[c] for c in cols]


# =========================================================
# Macro
# =========================================================

def upsert_daily_macro_structure(row: dict[str, Any]) -> None:
    """
    Required:
        as_of_date
        macro_state
    """
    sql, params = _build_upsert_sql(
        table="daily_macro_structure",
        row=row,
        conflict_cols=["as_of_date"],
    )
    execute(sql, params)


def get_daily_macro_structure(as_of_date: date | str) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_macro_structure
    WHERE as_of_date = %s
    """
    return fetch_one(sql, [_to_date_str(as_of_date)])


def get_latest_macro_structure(as_of_date: date | str) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_macro_structure
    WHERE as_of_date <= %s
    ORDER BY as_of_date DESC
    LIMIT 1
    """
    return fetch_one(sql, [_to_date_str(as_of_date)])


# =========================================================
# Sector
# =========================================================

def upsert_daily_sector_structure(row: dict[str, Any]) -> None:
    """
    Required:
        as_of_date
        sector_name
        sector_state
    """
    sql, params = _build_upsert_sql(
        table="daily_sector_structure",
        row=row,
        conflict_cols=["as_of_date", "sector_name"],
    )
    execute(sql, params)


def get_daily_sector_structure(
    *,
    sector_name: str,
    as_of_date: date | str,
) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_sector_structure
    WHERE sector_name = %s
      AND as_of_date = %s
    """
    return fetch_one(sql, [sector_name, _to_date_str(as_of_date)])


def get_latest_sector_structure(
    *,
    sector_name: str,
    as_of_date: date | str,
) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_sector_structure
    WHERE sector_name = %s
      AND as_of_date <= %s
    ORDER BY as_of_date DESC
    LIMIT 1
    """
    return fetch_one(sql, [sector_name, _to_date_str(as_of_date)])


# =========================================================
# Symbol
# =========================================================

def upsert_daily_symbol_structure(row: dict[str, Any]) -> None:
    """
    Required:
        as_of_date
        symbol
        symbol_state
    """
    sql, params = _build_upsert_sql(
        table="daily_symbol_structure",
        row=row,
        conflict_cols=["as_of_date", "symbol"],
    )
    execute(sql, params)


def get_daily_symbol_structure(
    *,
    symbol: str,
    as_of_date: date | str,
) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_symbol_structure
    WHERE symbol = %s
      AND as_of_date = %s
    """
    return fetch_one(sql, [symbol, _to_date_str(as_of_date)])


def get_latest_symbol_structure(
    *,
    symbol: str,
    as_of_date: date | str,
) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_symbol_structure
    WHERE symbol = %s
      AND as_of_date <= %s
    ORDER BY as_of_date DESC
    LIMIT 1
    """
    return fetch_one(sql, [symbol, _to_date_str(as_of_date)])


# =========================================================
# Runtime bundle
# =========================================================

def get_latest_daily_structure_bundle(
    *,
    symbol: str,
    sector_name: str,
    as_of_date: date | str,
) -> dict[str, Any]:
    """
    Runtime 用：
        给一个当前 bar 日期，加载最近可用的 daily slow context。

    注意：
        调用方需要保证 as_of_date 不使用未来日期。
        日内交易时通常传 previous trading date 或 current date，
        SQL 会自动取 <= as_of_date 的最近记录。
    """
    return {
        "macro": get_latest_macro_structure(as_of_date),
        "sector": get_latest_sector_structure(
            sector_name=sector_name,
            as_of_date=as_of_date,
        ),
        "symbol": get_latest_symbol_structure(
            symbol=symbol,
            as_of_date=as_of_date,
        ),
    }


# =========================================================
# Run meta
# =========================================================

def create_daily_structure_run(
    *,
    run_id: str,
    start_date: date | str,
    end_date: date | str,
    symbols: list[str] | None = None,
    sectors: list[str] | None = None,
) -> None:
    sql = """
    INSERT INTO public.daily_structure_runs (
        run_id,
        start_date,
        end_date,
        status,
        symbols,
        sectors,
        started_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ON CONFLICT (run_id)
    DO UPDATE SET
        status = EXCLUDED.status,
        start_date = EXCLUDED.start_date,
        end_date = EXCLUDED.end_date,
        symbols = EXCLUDED.symbols,
        sectors = EXCLUDED.sectors,
        started_at = CURRENT_TIMESTAMP,
        finished_at = NULL,
        error_message = NULL
    """
    execute(
        sql,
        [
            run_id,
            _to_date_str(start_date),
            _to_date_str(end_date),
            "RUNNING",
            symbols or [],
            sectors or [],
        ],
    )


def finish_daily_structure_run(run_id: str) -> None:
    sql = """
    UPDATE public.daily_structure_runs
    SET status = 'SUCCEEDED',
        finished_at = CURRENT_TIMESTAMP,
        error_message = NULL
    WHERE run_id = %s
    """
    execute(sql, [run_id])


def fail_daily_structure_run(run_id: str, error_message: str) -> None:
    sql = """
    UPDATE public.daily_structure_runs
    SET status = 'FAILED',
        finished_at = CURRENT_TIMESTAMP,
        error_message = %s
    WHERE run_id = %s
    """
    execute(sql, [error_message, run_id])


def get_daily_structure_run(run_id: str) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_structure_runs
    WHERE run_id = %s
    """
    return fetch_one(sql, [run_id])


def get_recent_daily_structure_runs(limit: int = 20) -> list[dict[str, Any]]:
    sql = """
    SELECT *
    FROM public.daily_structure_runs
    ORDER BY started_at DESC
    LIMIT %s
    """
    return fetch_all(sql, [limit])

def get_last_successful_daily_structure_run() -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM public.daily_structure_runs
    WHERE status = 'SUCCEEDED'
    ORDER BY end_date DESC, finished_at DESC
    LIMIT 1
    """
    return fetch_one(sql)


def finish_daily_structure_run_with_end_date(
    *,
    run_id: str,
    actual_end_date: date | str,
) -> None:
    sql = """
    UPDATE public.daily_structure_runs
    SET status = 'SUCCEEDED',
        end_date = %s,
        finished_at = CURRENT_TIMESTAMP,
        error_message = NULL
    WHERE run_id = %s
    """
    execute(sql, [_to_date_str(actual_end_date), run_id])