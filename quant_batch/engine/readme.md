# 📦 engine 模块

## 🧠 模块定位

`engine` 是量化系统的**编排层（Orchestration Layer）**，负责把各个独立模块组合成完整交易链路：

feature → signal → position

它的核心职责：

- 屏蔽底层计算复杂性（macro / sector / symbol）
- 提供统一的数据结构（feature_df）
- 输出可用于回测 / 实盘的交易决策链路
- 保证系统单向时序（no future leak）

---

## 🧩 模块组成

---

# 1️⃣ feature_engine.py

## 核心函数

build_feature_frame(...)

---

## 功能

- 聚合：
  - symbol 模块
  - sector 模块
  - macro 模块
- 统一生成：
  - indicators（L1）
  - factors（L2）
  - contexts / states（结构层）
- 时间对齐（alignment）
- 输出统一结构

---

## 输入

- symbol_df
- sector_etf_df
- sector_member_dfs
- spy_df
- vix_df
- hy_oas_df
- config_bundle

---

## 输出

pd.DataFrame

结构：

- index = 时间序列
- symbol_* 
- sector_*（_sector 后缀）
- macro_*（_macro 后缀）

---

# 2️⃣ signal_engine.py

## 核心函数

compute_action_signals(feature_df, config)

---

## 功能

基于结构输出交易意图：

- trend → 持仓 / 加仓
- range → 做T
- risk → 降仓 / 避免

---

## 输入

- feature_df

关键字段：

- symbol_state
- sector_state_sector
- macro_state_macro
- symbol_range_position

---

## 输出

ActionSignal：

- BUY
- SELL
- HOLD
- REDUCE
- AVOID

---

## 特点

- 单向时序（无未来数据）
- 状态驱动
- 带 cooldown 稳定机制
- 不涉及仓位管理

---

# 3️⃣ position_engine.py

---

## 🧱 Basic 版本（V1）

### 定位

最小可用执行引擎，用于：

- 打通全链路
- 快速验证策略
- 简单回测

---

### 能力

- 固定手数交易（entry/add/reduce/sell）
- 最大仓位控制
- cooldown 控制
- price gap 控制

---

### 输入

- action_signal
- close

---

### 输出

- position_action
- position_delta
- position_size
- executed_price

---

### 特点

- 简单
- 可解释
- 不感知成本
- 不感知盈亏

---

## ⚙️ Enhanced 版本（V2）

### 定位

增强执行引擎，更接近真实交易系统

---

### 新增能力

#### 1. 成本管理

- position_avg_cost
- position_unrealized_pnl_pct

---

#### 2. 执行原因

execution_reason，例如：

- buy_executed
- buy_blocked_by_cooldown
- buy_blocked_by_price_gap
- buy_blocked_by_loss_guard

---

#### 3. 交易节奏控制

- buy_count_since_reset
- sell_count_since_reset
- MAX_BUY_COUNT_PER_CYCLE

---

#### 4. 仓位区间控制

- 高仓位限制继续加仓

---

#### 5. 亏损保护

- 限制在亏损中继续补仓

---

### 输出（完整）

- position_action
- position_delta
- position_size
- executed_price

- position_avg_cost
- position_unrealized_pnl_pct
- execution_reason

- buy_count_since_reset
- sell_count_since_reset

---

### 特点

- 更贴近真实交易
- 风控内生
- 完全确定性（deterministic）
- 无未来数据

---

## 🔄 数据流

raw data  
↓  
feature_engine  
↓  
feature_df  
↓  
signal_engine  
↓  
action_signal  
↓  
position_engine  
↓  
position_action  

---

## 🧭 设计原则

### 1. 不预测，只分类

market → regime → action

---

### 2. 结构优先

L2（state）决定行为  
L3（signal / position）执行

---

### 3. Signal ≠ Execution

signal = 可以做  
position = 要不要做  

---

### 4. 风控内生

- 仓位
- 成本
- 节奏
- 风险

全部在 position engine 内实现

---

### 5. 单向时序

所有决策满足：

t 时刻只依赖 ≤ t 的数据

---

## 🔥 一句话总结

engine = Alpha Stack 的执行大脑

负责把：

市场结构 → 信号 → 仓位 → 交易执行

串成完整系统