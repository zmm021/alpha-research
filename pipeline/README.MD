# 📦 Pipeline 使用说明

## 🚀 1. 每日增量数据拉取

用于日常运行，从上次 offset 自动拉取到昨天（支持自动补数据）。

### 命令

```bash
python3 -m pipeline.ingestion --sector uranium
python3 -m pipeline.ingestion --marco
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
python3 -m pipeline.ingestion_backfill backfill-year --macro --year 2025
python3 -m pipeline.ingestion_backfill backfill-year --symbol UUUU --year 2025
```
## 🚀 📆 2. 回填单月数据（Backfill Month）
 
### 命令

```bash
python3 -m pipeline.ingestion_backfill backfill-month --symbol UUUU --month 2025-01
python3 -m pipeline.ingestion_backfill backfill-month --sector uranium --month 2025-01
python3 -m pipeline.ingestion_backfill backfill-month --macro --month 2025-01
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

## 🚀  3. backtest
```bash
python3 -m pipeline.backtest --symbol UUUU --sector rare_earth  --sector-etf REMX --start-date 2025-01-01 --end-date 2025-12-31
```
run_backtest_action_pipeline
├─ _load_config_bundle
├─ load_symbol_bars
├─ load_sector_bars
├─ _resolve_sector_etf_df
├─ load_macro_bars
├─ _resolve_macro_inputs
├─ build_feature_frame
├─ compute_action_signals
├─ PositionTrackerEngine(...)
├─ DecisionContextBuilder(...)
├─ PositionEngine(...)
├─ DecisionEngine(...)
└─ for each bar:
   ├─ tracker.on_bar
   ├─ tracker.get_snapshot
   ├─ ctx_builder.build
   ├─ position_engine.propose
   ├─ decision_engine.decide
   ├─ tracker.on_buy / on_reduce / on_sell / on_force_exit
   └─ tracker.get_snapshot

build_feature_frame
├─ compute_symbol_indicators
├─ compute_symbol_factors
├─ compute_symbol_contexts
├─ compute_symbol_states
├─ compute_sector_indicators
├─ compute_sector_factors
├─ compute_sector_contexts
├─ compute_sector_states
├─ compute_macro_indicators
├─ compute_macro_factors
├─ compute_macro_contexts
└─ compute_macro_states

signals = compute_action_signals(feature_df, config_bundle["signal"])
compute_action_signals
├─ _validate_required_columns
├─ compute_regime
├─ _trend_signal
├─ _range_signal
├─ _risk_signal
├─ _apply_global_overrides
├─ _apply_cooldown
└─ _collapse_repeated_signal
signal_engine 直接依赖 regime_engine.compute_regime。所以当前不是只有 decision_context 在用 regime，signal_engine 自己也会算一遍 regime。

## 🚀  4. optimization 贝叶斯信号参数优

该模块用于优化 Alpha Stack 中的信号参数（signal parameters），不影响现有的 backtest pipeline。

---

### 一、核心目标

本优化模块的目标是：

> 提升 **信号质量（signal quality）**，而不是预测价格或直接优化收益

优化逻辑基于：

- feature engine（特征计算）
- signal engine（信号生成）
- signal evaluator（信号评估）

---

### 二、整体流程

每一轮（trial）执行以下步骤：

1. 加载基础配置（config bundle）
2. 生成一组候选参数（candidate params）
3. 覆盖原始 config（仅覆盖部分参数）
4. 构建 feature frame
5. 生成 action signal（buy / sell / reduce / avoid）
6. 使用 evaluator 计算信号质量评分
7. Optuna 根据评分更新参数搜索策略

---

### 三、系统结构
```bash
python3 -m pipeline.optimization \
  --symbol UUUU \
  --sector rare_earth \
  --sector-etf REMX \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --n-trials 20 \
  --study-name uuuu_signal_opt
  ```
## 🚀  5. Realtime simulation
```bash
python3 -m pipeline.realtime_simulation
```