# Alpha Stack Indicators 使用说明（最终版）

本系统指标模块统一采用 **“序列计算 + Snapshot 输出”** 的设计。

---

# 🧱 核心设计

所有指标函数分为两类：

## 1️⃣ Feature Series（基础能力）

```python
build_xxx_feature_series(df)
```

- 输入：一段时间序列（bars）
- 输出：每个时间点的完整指标

👉 用于：
- offline research
- backtest
- training
- 调试 / 可视化

---

## 2️⃣ Snapshot（对外接口）

```python
build_xxx_snapshot(df)
```

- 输入：一段时间序列（window）
- 输出：最后一个时间点的指标（单行）

👉 用于：
- offline daily pipeline
- online realtime system

---

# 🧠 关键原则

## ✔ 指标函数不关心频率

函数只关心：

- 输入是一个有序的 bar 序列
- 包含 OHLCV

它不关心：

- 是 1min / 5min / 1D

---

## ✔ 频率由上层决定

| 场景 | 输入 |
|------|------|
| realtime | 1min / 5min bars |
| daily snapshot | daily bars（由 minute 聚合） |

---

## ✔ 输入必须是“序列”，不是单点

即使只输出一个 snapshot：

- 输入仍然需要一段历史 window
- 因为指标依赖历史（MA / RSI / MACD 等）

---

# 📦 各模块说明

---

## 1️⃣ Primitive Indicators（L1）

### Feature Series

```python
build_primitive_feature_series(df)
```

### Snapshot

```python
build_primitive_snapshot(df)
```

输入：

- 单个标的 OHLCV 序列

输出：

- MA / EMA
- RSI
- MACD
- ATR
- Bollinger
- Return
- Volume 特征

---

## 2️⃣ Derived Indicators（L2 输入特征）

### Feature Series

```python
build_derived_feature_series(df)
```

### Snapshot

```python
build_derived_snapshot(df)
```

输入：

- Primitive 输出

输出：

- trend_strength
- volatility regime
- range efficiency
- momentum state

---

## 3️⃣ Macro Indicators（L0）

### Feature Series

```python
build_macro_feature_series(daily_map)
```

### Snapshot

```python
build_macro_snapshot(daily_map)
```

输入：

- 多个宏观资产（SPY / VIX / TLT 等）

输出：

- risk_on / risk_off
- macro trend
- volatility regime

---

## 4️⃣ Sector Indicators（L0）

### Feature Series

```python
build_sector_feature_series(...)
```

### Snapshot

```python
build_sector_snapshot(...)
```

输入：

- sector ETF 或成员

输出：

- sector strength
- breadth
- relative strength

---

# 🔁 Pipeline 使用方式

---

## 🟢 Offline Daily Pipeline

```python
# 1. minute → daily 聚合
daily_df = aggregate_to_daily(minute_df)

# 2. 计算指标
primitive = build_primitive_snapshot(daily_df)
derived = build_derived_snapshot(build_primitive_feature_series(daily_df))

macro = build_macro_snapshot(macro_map)
sector = build_sector_snapshot(sector_map, ...)
```

---

## 🔵 Online Realtime

```python
# 最近一段分钟 bars
minute_df = get_recent_bars()

primitive_rt = build_primitive_snapshot(minute_df)
derived_rt = build_derived_snapshot(
    build_primitive_feature_series(minute_df)
)
```

---

# 📏 历史数据要求

输入序列长度必须 ≥ 最大窗口

建议：

- daily：~300 bars
- minute：100~300 bars

---

# 🚫 不要做的事情

❌ 不要只给单个 bar  
❌ 不要用 snapshot 作为输入再算基础指标  
❌ 不要让指标函数负责数据聚合  
❌ 不要写 DB 逻辑  

---

# 🧩 数据流总结

```text
raw data (minute)
    ↓
聚合成目标频率（daily / 1min）
    ↓
feature_series
    ↓
snapshot（最后一行）
    ↓
L2 / L3
```

---

# 🚀 一句话总结

> 指标函数负责“计算”，不负责“数据准备”，不负责“存储”

---

