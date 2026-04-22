# Quant 模块说明（Alpha Stack）

## 🧠 一、模块目标

`quant` 模块实现的是一个**基于市场结构的多层交易系统**。

它的职责是：

```
原始市场数据 → 特征 → 状态 → 行为信号（action_signal）
```

---

## 🧩 二、整体架构

```
raw data
  ↓
feature_engine
  ↓
macro / sector / symbol states
  ↓
signal_engine
  ↓
action_signal（买卖信号）
  ↓
position_engine（未来）
```

---

## 📦 三、目录结构

```
quant/
  common/        # 基础定义（枚举、常量、数据结构）
  macro/         # 宏观层计算
  sector/        # 板块层计算（多序列聚合）
  symbol/        # 个股层计算

  engine/
    feature_engine.py   # 特征构建（核心）
    signal_engine.py    # 生成买卖信号
```

---

## 🔹 四、Feature Engine（特征引擎）

### 核心接口

```python
build_feature_frame(
    symbol_df,
    sector_etf_df,
    sector_member_dfs,
    spy_df,
    vix_df,
    hy_oas_df,
    config_bundle,
)
```

---

### 输入说明

```
symbol_df           → 目标股票（主时间轴）
sector_etf_df       → 板块ETF
sector_member_dfs   → 板块成分股（dict）
spy_df / vix_df     → 宏观数据
hy_oas_df           → 信用利差
config_bundle       → 配置（symbol / sector / macro）
```

---

### 输出说明

返回一个 `pd.DataFrame`，以 **symbol 时间轴为基准对齐**：

```
index = symbol timestamp

columns =
  symbol 指标 / 因子 / context / state

  sector 指标 / context / state（带 _sector 后缀）

  macro 指标 / context / state（带 _macro 后缀）
```

---

### 示例调用

```python
features = build_feature_frame(
    symbol_df,
    sector_etf_df,
    sector_member_dfs,
    spy_df,
    vix_df,
    hy_oas_df,
    config_bundle,
)
```

---

## 🔹 五、Signal Engine（信号引擎）

### 核心接口

```python
compute_action_signals(feature_df, config)
```

---

### 输入

```
feature_df → feature_engine 输出结果
config     → signal 配置
```

---

### 输出

```python
pd.Series[ActionSignal]
```

枚举定义：

```python
class ActionSignal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    AVOID = "avoid"
```

---

### 示例调用

```python
signals = compute_action_signals(features, config_bundle)
features["action_signal"] = signals
```

---

## 🧠 六、核心概念

### 1️⃣ State（结构层）

```
macro_state   → risk_on / neutral / risk_off
sector_state  → leading / mixed / weak
symbol_state  → trend / pullback / range / risk
```

👉 表示“市场处于什么结构”

---

### 2️⃣ Action Signal（意图层）

```
BUY / SELL / HOLD / REDUCE / AVOID
```

👉 表示“应该做什么”

⚠️ 不包含仓位信息

---

### 3️⃣ Position（执行层，未来）

```
买多少 / 卖多少 / 不动
```

👉 独立模块处理（风控 + 仓位）

---

## 🧭 七、设计原则

1. 不预测价格，只识别结构  
2. state 决定一切（state-driven system）  
3. signal（意图）与 position（执行）解耦  
4. 多频数据统一对齐到 symbol 时间轴  
5. 避免未来数据（仅 forward fill）

---

## 🔥 八、完整使用流程

```python
# Step 1: 特征构建
features = build_feature_frame(...)

# Step 2: 信号生成
signals = compute_action_signals(features, config_bundle)

# Step 3: 合并
features["action_signal"] = signals
```

---

## 🚀 九、系统阶段

当前已完成：

```
✔ feature_engine
✔ state（macro / sector / symbol）
✔ signal_engine（action_signal）
```

下一步：

```
→ position_engine（仓位 + 风控）
```

---

## 🧩 十、一句话总结

```
state → signal → position
```

这是一个**结构驱动的交易系统**，而不是预测系统。


risk_engine   → risk_output
tracker       → snapshot
alpha_signal  → signal

一起 → decision_context