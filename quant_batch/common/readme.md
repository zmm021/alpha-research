# common 模块

## 🧠 模块定位

`common` 是整个 quant 系统的**基础定义层（foundation layer）**，用于统一：

- 命名（指标 / 因子 / context）
- 状态（macro / sector / symbol）
- 数据结构（跨模块传递）
- 配置读取方式

它不包含任何计算逻辑，只提供**全局一致的语言和结构**。

---

## 📦 模块内容

### 1️⃣ enums.py

定义系统中的离散状态与信号：

```python
MacroState
SectorState
SymbolState
ActionSignal
```

👉 用于：

- 表达市场结构（state）
- 表达交易意图（action_signal）

---

### 2️⃣ constants.py

统一所有字段命名：

```python
Indicators
Factors
Contexts
```

👉 作用：

- 避免字符串硬编码
- 防止拼写错误
- 保证跨模块一致性

---

### 3️⃣ schemas.py

定义核心数据结构：

```python
IndicatorOutput
FactorOutput
ContextOutput
StateOutput
LayerSnapshot
```

👉 用于：

- 在不同层之间传递数据
- 保持接口稳定

---

### 4️⃣ config_loader.py

负责加载配置（yaml）：

```python
load_config(...)
load_configs(...)
```

👉 实现：

- 参数与代码解耦
- 支持后续优化 / 调参

---

## 🧭 设计原则

1. **只做定义，不做计算**
2. **全局唯一命名（single source of truth）**
3. **跨模块共享，不依赖具体业务逻辑**
4. **为扩展（feature / strategy / optimization）提供稳定接口**

---

## 🔥 一句话总结

```
common = 整个系统的“语言层”和“协议层”
```

所有模块（macro / sector / symbol / engine）都依赖它来保持一致性。
