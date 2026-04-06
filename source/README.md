# Ingestion CLI

这个 README 只描述 `ingestion` 下的 IBKR 历史数据拉取 CLI。

## 目录建议

```text
market_research/
├── config.py
├── ingestion/
│   ├── __init__.py
│   ├── cli.py
│   ├── ib_data_lib.py
│   └── ib_data_store.py
```
 

## 支持的命令 （在Market Research文件夹下执行）

### 1. 拉取某一整年的分钟历史数据

```bash
python3 -m ingestion.cli pull-year --symbol UUUU --year 2025 --use-rth
```

### 2. 拉取某一整个月的分钟历史数据

```bash
python3 -m ingestion.cli pull-month --symbol UUUU --month 2025-01 --use-rth
```

### 3. 拉取某一天的分钟历史数据

```bash
python3 -m ingestion.cli pull-day --symbol UUUU --date 2025-01-01 --use-rth
```

## 输出位置

输出目录由根目录 `config.py` 控制，代码会调用：

- `get_historical_dir(symbol)`

最终文件默认会存到类似：

```text
Data/market/UUUU/historical/
```

文件名示例：

```text
UUUU_year_2015.parquet
UUUU_month_2025_01.parquet
UUUU_day_2025_01_01.parquet
```

## 依赖的 config.py 字段

根目录 `config.py` 需要至少包含：

- `IB_HOST`
- `IB_PORT`
- `IB_CLIENT_ID`
- `FILE_FORMAT`
- `get_historical_dir(symbol)`
 
 
