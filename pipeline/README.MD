# 📦 Pipeline 使用说明

## 🚀 1. 每日增量数据拉取

用于日常运行，从上次 offset 自动拉取到昨天（支持自动补数据）。

### 命令

```bash
python3 -m pipeline.ingestion --sector uranium
```

行为说明
	•	获取该 sector 下所有 symbol
	•	从 meta_symbol_offset 表中读取每个 symbol 的 offset
	•	从 offset 的下一个 business day 开始拉取
	•	拉取到 昨天（自动跳过周末）
	•	如果中间漏跑，会自动补齐缺失数据
	•	所有数据成功后，更新 offset

## 🚀 📆 2. 回填整年数据（Backfill Year）

用于初始化或补历史数据。
### 命令

```bash
python3 -m pipeline.ingestion_backfill backfill-year --sector uranium --year 2025
```
## 🚀 📆 2. 回填单月数据（Backfill Month）
 
### 命令

```bash
python3 -m pipeline.ingestion_backfill backfill-month --sector uranium --month 2025-01
```
行为说明
	•	拉取指定月份的数据
	•	调用 ingestion 层的 pull_month
	•	完成后，将 offset 更新为 该月最后一个 business day

🧠 重要说明
	•	offset 是 按 symbol 单独存储
	•	存储位置：meta_symbol_offset 表
	•	如果 symbol 没有 offset：默认从 2025-01-01 开始拉取
    •	当前 business day 定义：周一到周五（暂未处理节假日）