# 拉一年历史数据
python3 cli.py backfill --symbol UUUU --use-rth

# 启动实时监听
python3 cli.py listen

# 测试监听（跑50次）
python3 cli.py listen --max-loops 50



#Export parquet to csv
python3 parquet_to_csv.py \
  --symbol UUUU \
  --input "/Users/mingmingzhang/Documents/alpha stack/Data/UUUU/historical/UUUU_year.parquet" \
  --output "/Users/mingmingzhang/Documents/alpha stack/Trading OS/src/main/java/com/trading/os/data/market/UUUU_1m.csv" \
  --days 30