from __future__ import annotations

from postgres.pg_client import fetch_all,execute


def get_sector_symbols(sector_name: str, asset_type: str | None = None) -> list[str]:
    sql = """
    SELECT s.symbol
    FROM symbol_sector_map m
    JOIN sectors sec ON m.sector_id = sec.sector_id
    JOIN symbols s ON m.symbol = s.symbol
    WHERE sec.sector_name = %s
    """

    params: list[object] = [sector_name]

    if asset_type is not None:
        sql += " AND s.asset_type = %s"
        params.append(asset_type)

    sql += " ORDER BY s.symbol"

    rows = fetch_all(sql, params)
    return [row["symbol"] for row in rows]


def get_sector_symbols_with_meta(sector_name: str) -> list[dict]:
    sql = """
    SELECT s.symbol, s.asset_type, s.exchange, m.weight
    FROM symbol_sector_map m
    JOIN sectors sec ON m.sector_id = sec.sector_id
    JOIN symbols s ON m.symbol = s.symbol
    WHERE sec.sector_name = %s
    ORDER BY s.symbol
    """
    return fetch_all(sql, [sector_name])

def get_all_sectors() -> list[str]:
    sql = """
    SELECT sector_name
    FROM public.sectors
    ORDER BY sector_name
    """
    rows = fetch_all(sql)
    return [row["sector_name"] for row in rows]

def get_related_symbols(symbol: str, sector_name: str | None = None) -> list[str]:
    sql = """
    SELECT DISTINCT s2.symbol
    FROM public.symbol_sector_map m1
    JOIN public.symbol_sector_map m2
        ON m1.sector_id = m2.sector_id
    JOIN public.sectors sec
        ON m1.sector_id = sec.sector_id
    JOIN public.symbols s2
        ON m2.symbol = s2.symbol
    WHERE m1.symbol = %s
    """

    params: list[object] = [symbol]

    if sector_name is not None:
        sql += " AND sec.sector_name = %s"
        params.append(sector_name)

    sql += " ORDER BY s2.symbol"

    rows = fetch_all(sql, params)
    return [row["symbol"] for row in rows]
def get_symbol_sectors(symbol: str) -> list[str]:
    sql = """
    SELECT sec.sector_name
    FROM public.symbol_sector_map m
    JOIN public.sectors sec
        ON m.sector_id = sec.sector_id
    WHERE m.symbol = %s
    ORDER BY sec.sector_name
    """
    rows = fetch_all(sql, [symbol])
    return [row["sector_name"] for row in rows]

def get_macro_groups() -> list[str]:
    sql = """
    SELECT macro_group_name
    FROM public.macro_groups
    ORDER BY macro_group_name
    """
    rows = fetch_all(sql)
    return [row["macro_group_name"] for row in rows]
    
def get_macro_symbols() -> list[str]:
    sql = """
    SELECT DISTINCT s.symbol
    FROM public.symbol_macro_map m
    JOIN public.symbols s ON m.symbol = s.symbol
    ORDER BY s.symbol
    """
    rows = fetch_all(sql)
    return [row["symbol"] for row in rows]
#✅ 2. 按 macro group 获取 symbols
#👉 用于分组环境分析
def get_macro_symbols_by_group(group_name: str) -> list[str]:
    sql = """
    SELECT s.symbol
    FROM public.symbol_macro_map m
    JOIN public.macro_groups g ON m.macro_group_id = g.macro_group_id
    JOIN public.symbols s ON m.symbol = s.symbol
    WHERE g.macro_group_name = %s
    ORDER BY s.symbol
    """
    rows = fetch_all(sql, [group_name])
    return [row["symbol"] for row in rows]
#获取 macro symbols + role + weight（后面一定会用）
#用于计算 composite indicator
def get_macro_symbols_with_meta() -> list[dict]:
    sql = """
    SELECT
        s.symbol,
        g.macro_group_name,
        m.role,
        m.weight
    FROM public.symbol_macro_map m
    JOIN public.macro_groups g ON m.macro_group_id = g.macro_group_id
    JOIN public.symbols s ON m.symbol = s.symbol
    ORDER BY g.macro_group_name, s.symbol
    """
    return fetch_all(sql)


def get_last_offset(symbol: str) -> str | None:
    sql = """
    SELECT offset_date
    FROM public.meta_symbol_offset
    WHERE symbol = %s
    """
    rows = fetch_all(sql, [symbol])

    if not rows:
        return None

    return str(rows[0]["offset_date"])

def update_offset(symbol: str, new_offset: str) -> None:
    current = get_last_offset(symbol)

    if current is not None and new_offset <= current:
        # 不更新（防止回退）
        return

    sql = """
    INSERT INTO public.meta_symbol_offset (symbol, offset_date)
    VALUES (%s, %s)
    ON CONFLICT (symbol)
    DO UPDATE SET
        offset_date = EXCLUDED.offset_date,
        updated_at = CURRENT_TIMESTAMP
    """
    execute(sql, [symbol, new_offset])

def get_all_offsets() -> dict[str, str]:
    sql = """
    SELECT symbol, offset_date
    FROM public.meta_symbol_offset
    """
    rows = fetch_all(sql)

    return {
        row["symbol"]: str(row["offset_date"])
        for row in rows
    }