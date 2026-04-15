# engine 模块

## 🧠 模块定位

`engine` 是 quant 系统的**编排层（orchestration layer）**，负责将各个计算模块（macro / sector / symbol）组合起来，形成统一的数据输出与交易信号。

它的核心作用是：

- 屏蔽底层复杂计算逻辑
- 提供统一接口给 pipeline / 回测 / 实盘系统
- 连接 feature → signal →（未来）position

---

## 📦 模块内容

### 1️⃣ feature_engine.py

核心函数：

```python
build_feature_frame(...)
```

---

### 功能

- 调用：
  - symbol 模块
  - sector 模块
  - macro 模块
- 统一生成：
  - indicators / factors / contexts / states
- 执行：
  - 时间对齐（alignment）
- 输出：
  - 单一 feature_df（统一结构）

---

### 输入

```python
symbol_df
sector_etf_df
sector_member_dfs
spy_df
vix_df
hy_oas_df
config_bundle
```

---

### 输出

```python
pd.DataFrame
```

结构：

```text
index = symbol timeline

columns =
  symbol_* 
  sector_* （带 _sector 后缀）
  macro_* （带 _macro 后缀）
```

---

### 示例

```python
features = build_feature_frame(...)
```

---

## 2️⃣ signal_engine.py

核心函数：

```python
compute_action_signals(feature_df, config)
```

---

### 功能

- 基于：
  - macro_state
  - sector_state
  - symbol_state
- 输出交易意图（action_signal）

---

### 输出

```python
pd.Series[ActionSignal]
```

枚举：

```python
BUY / SELL / HOLD / REDUCE / AVOID
```

---

### 示例

```python
signals = compute_action_signals(features, config)
features["action_signal"] = signals
```

---

## 🔄 数据流

```text
raw data
  ↓
feature_engine
  ↓
feature_df（统一结构）
  ↓
signal_engine
  ↓
action_signal
```

---

## 🧭 设计原则

1. **只做编排，不做底层计算**
2. **统一输出结构（single feature frame）**
3. **对齐逻辑集中处理（避免 pipeline 复杂化）**
4. **模块解耦（feature / signal / position 分离）**

---

## 🔥 一句话总结

```
engine = 系统的大脑（orchestrator）
```

负责把分散的计算模块组合成一个完整的交易输入与信号输出流程。
