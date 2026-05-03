# Offline Daily Structure Pipeline

## Purpose

`quant/offline` 负责计算 Alpha Stack 的 **daily slow variables**，并将结果写入 Postgres。

这些变量用于 runtime 阶段作为慢结构输入，包括：

- macro daily structure
- sector daily structure
- symbol daily structure

核心原则：

```text
Offline = 计算慢变量并入库
Runtime = 读取慢变量 + 计算快变量 + 决策
```

---

## What It Computes

Pipeline 会调用现有 batch 计算函数：

```text
indicators → factors → structure scores → states
```

并写入以下表：

```text
daily_macro_structure
daily_sector_structure
daily_symbol_structure
daily_structure_runs
```

---

## Incremental Logic

每次运行时：

```text
1. 查询 daily_structure_runs 中最后一条 SUCCEEDED run
2. 如果没有历史 run，从 default_start_date 开始
3. 如果有历史 run，从 last_end_date + 1 开始
4. end_date = yesterday
5. 为 rolling 指标向前加载 lookback_days
6. 只写入 run_start ~ run_end 的新结果
7. 最后更新 run meta
```

示例：

```text
last_end_date = 2026-01-05
today = 2026-05-02

run_start = 2026-01-06
run_end = 2026-05-01
start_load = run_start - lookback_days
```

---

## Config

配置文件：

```text
quant/offline/daily_structure_config.yaml
```

示例：

```yaml
daily_structure:
  default_start_date: "2025-01-01"
  base_path: "data/market"
  config_dir: "quant/config"
  lookback_days: 1200

  macro:
    enabled: true

  sectors:
    - sector_name: "rare_earth"
      sector_etf: "REMX"
      member_asset_type: null

  symbols:
    - "UUUU"
    - "MP"
    - "CRML"
```

---

## How To Run

在 repo 根目录执行：

```bash
python3 -m quant.offline.daily_structure_pipeline
```

或指定 config：

```bash
python3 -m quant.offline.daily_structure_pipeline \
  --config quant/offline/daily_structure_config.yaml
```

---

## Notes

- 本 pipeline 使用 batch 计算（pandas rolling），不使用 engine 的 warmup/update
- Macro / Sector / Symbol Engine 主要用于未来 realtime/incremental
- Daily slow variables 不应使用 intraday 数据
- Runtime 应从 Postgres 加载最近有效的 daily structure
- 若某 symbol 或 sector 无数据，则自动跳过

---

## Role in Alpha Stack

```text
Offline Daily Pipeline
    ↓
Postgres daily structure tables
    ↓
Runtime S1StructureContext
    ↓
S2 / S3 / S4 / S5 / S6 decision chain
```

总结：

```text
offline 负责计算“世界观”
runtime 负责基于世界观做决策
```
