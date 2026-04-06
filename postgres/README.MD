# Postgres CLI Usage

This CLI provides simple access to sector and symbol relationships.

## 1. Get all sectors

```bash
python3 -m postgres.meta_cli get-sectors
```

## 2. Get symbols in a sector

```bash
python3 -m postgres.meta_cli get-sector-symbols --sector uranium
```

Optional filter by asset type:

```bash
python3 -m postgres.meta_cli get-sector-symbols --sector uranium --asset-type stock
```

## 3. Get symbols in a sector with metadata

```bash
python3 -m postgres.meta_cli get-sector-symbols-meta --sector rare_earth
```

## 4. Get related symbols by shared sectors

```bash
python3 -m postgres.meta_cli get-related-symbols --symbol UUUU
python3 -m postgres.meta_cli get-related-symbols --symbol UUUU --sector uranium   #limit the sector
```

## 5. Get sectors for a symbol

```bash
python3 -m postgres.meta_cli get-symbol-sectors --symbol UUUU
```
## 6. Get all macro symbols

```bash
python3 -m postgres.meta_cli get-macro-symbols
```
## 7. Get macro symbols by group
```bash
python3 -m postgres.meta_cli get-macro-by-group --group market_index
```

## 8. Get all macro groups

```bash
python3 -m postgres.meta_cli get-macro-groups
```
## 9. Get macro symbols with metadata

```bash
python3 -m postgres.meta_cli get-macro-symbols-meta
```
# 获取pipeline offset
## 10. Get last offset for a symbol

```bash
python3 -m postgres.meta_cli get-offset --symbol UUUU
```

## 11. Update offset for a symbol
```bash
python3 -m postgres.meta_cli update-offset --symbol UUUU --date 2026-01-02
```

## 12. Get all symbol offsets
```bash
python3 -m postgres.meta_cli get-all-offsets
```