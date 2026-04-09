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

# 🚀 总结

- bar_utils：处理时间序列数据
- parquet_to_csv：文件格式转换
- parquet_chart：数据快速可视化

