# Utils 模块说明 

本模块用于处理时间序列数据（bar），主要服务于 pipeline 层。

---

# 📦 模块组成

## 1️⃣ bar_utils.py

用于处理 OHLCV 时间序列数据：

### 功能

- bar 聚合（分钟 → 5min / 15min / 1H / 1D）
- 多标的聚合
- 截取最近 N 条数据
- 按时间 + 窗口截取
- session_date 推断（用于日内分组）

---

### 常用函数

#### 1. 聚合 bar

```python
from utils.bar_utils import aggregate_ohlcv_bars, BarFrequency

daily_df = aggregate_ohlcv_bars(
    minute_df,
    target_freq=BarFrequency.DAY_1,
)
```

---

#### 2. 多标的聚合

```python
from utils.bar_utils import aggregate_ohlcv_bars_by_symbol

df = aggregate_ohlcv_bars_by_symbol(
    multi_df,
    symbol_col="symbol",
    target_freq=BarFrequency.DAY_1,
)
```

---

#### 3. 取最近 N 条

```python
from utils.bar_utils import filter_recent_bars

df = filter_recent_bars(df, n_bars=300)
```

---

#### 4. 按时间截取

```python
from utils.bar_utils import align_bar_window

df = align_bar_window(
    df,
    end_time="2026-04-08 10:30:00",
    n_bars=120,
)
```

---

#### 5. 一步完成（推荐）

```python
from utils.bar_utils import prepare_bar_window, BarFrequency

df = prepare_bar_window(
    minute_df,
    target_freq=BarFrequency.DAY_1,
    n_bars=300,
)
```

---

# 🗂 其他工具

## 2️⃣ parquet_to_csv.py

用于将 parquet 文件转换为 CSV。

### 使用方式

```bash
python parquet_to_csv.py input.parquet output.csv
```

或在代码中：

```python
from parquet_to_csv import parquet_to_csv

parquet_to_csv("data.parquet", "data.csv")
```

---

## 3️⃣ parquet_chart.py

用于快速查看 parquet 数据（画图 / 检查数据）。

### 使用方式

```bash
python parquet_chart.py data.parquet
```

或在代码中：

```python
from parquet_chart import plot_parquet

plot_parquet("data.parquet")
```

---

# 🧠 使用流程（简单版）

### Offline

```python
df = prepare_bar_window(
    minute_df,
    target_freq=BarFrequency.DAY_1,
    n_bars=300,
)
```

---

### Realtime

```python
df = prepare_bar_window(
    minute_df,
    n_bars=120,
)
```

---
## 📦 4️⃣ parquet_loader.py

用于从本地 `data/market` 目录加载 parquet 行情数据，支持：

- 单 symbol
- sector（多 symbol）
- macro（多 symbol）
- 按时间区间加载（`start_date` / `end_date`）
- 频率聚合（1min → 5min / 1h / 1d）
- 严格模式下缺失文件直接报错

---

### 🚀 使用方式

#### 1. 单个 Symbol

```python
from utils.parquet_loader import load_symbol_bars
from utils.bar_utls import BarFrequency

df = load_symbol_bars(
    base_path="data/market",
    symbol="UUUU",
    start_date="2025-01-01",
    end_date="2025-03-31",
    target_freq=BarFrequency.MIN_5,
    strict=True,
)
```
#### 2. Sector（返回多个序列）
```python
from utils.parquet_loader import load_sector_bars
from utils.bar_utls import BarFrequency

sector_data = load_sector_bars(
    base_path="data/market",
    sector_name="rare-earth",
    start_date="2025-01-01",
    end_date="2025-03-31",
    target_freq=BarFrequency.DAY_1,
    strict=True,
)

--return dict[str, pd.DataFrame]
```
#### 3. Macro（返回多个序列）
```python
from utils.parquet_loader import load_macro_bars
from utils.bar_utls import BarFrequency

macro_data = load_macro_bars(
    base_path="data/market",
    start_date="2025-01-01",
    end_date="2025-03-31",
    target_freq=BarFrequency.DAY_1,
    strict=True,
)

--return dict[str, pd.DataFrame]
```

---

### ⚙️ 功能说明

- 按目录结构自动加载 parquet：

```
data/market/{symbol}/historical/YYYY/YYYY-MM/YYYY-MM-DD.parquet
```

	
	•	自动拼接多天数据
	•	支持多 symbol 批量加载（sector / macro）
	•	支持频率聚合（通过 BarFrequency）
	•	返回标准化 bar 数据（统一 schema）
	•	sector / macro 的 symbol 列表来自 postgres.meta_repo
	•	默认支持三种时间模式：
	•	start_date + end_date
	•	year
	•	month
	•	strict=True 时，如果任意 business day 文件缺失，会直接报错
	•	strict=False 时，允许跳过缺失文件

---

### 🧠 返回结构说明

| 模式 | 返回类型 |
|------|----------|
| symbol | `pd.DataFrame` |
| sector | `dict[str, pd.DataFrame]` |
| macro | `dict[str, pd.DataFrame]` |

---

### 🔥 一句话总结

```
parquet_loader = 本地行情数据的统一读取入口（支持单标的 & 多标的）
```


# 🚀 总结

- bar_utils：处理时间序列数据
- parquet_to_csv：文件格式转换
- parquet_chart：数据快速可视化
- parquet_loader：数据快速可视化
