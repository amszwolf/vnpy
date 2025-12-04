# -*- coding: utf-8 -*-
"""
分析调试CSV文件
"""

import pandas as pd
import numpy as np
from pathlib import Path

# 读取最新的调试CSV文件
debug_dir = Path("output/debug")
csv_files = list(debug_dir.glob("debug_data_*.csv"))

if not csv_files:
    print("没有找到调试CSV文件")
    exit(1)

# 获取最新的文件
latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
print(f"分析文件: {latest_csv}\n")

# 读取数据
df = pd.read_csv(latest_csv)

print("=" * 80)
print("数据概览")
print("=" * 80)
print(f"总记录数: {len(df)}")
print(f"时间范围: {df['datetime'].iloc[0]} 至 {df['datetime'].iloc[-1]}")

print("\n" + "=" * 80)
print("Price MACD 统计")
print("=" * 80)
print(df[['price_macd', 'price_macd_signal', 'price_macd_hist', 'price_xlpl_phase', 'price_cross']].describe())

# 检查MACD交叉
df['macd_diff'] = df['price_macd'] - df['price_macd_signal']
df['prev_macd_diff'] = df['macd_diff'].shift(1)
df['cross_up'] = (df['macd_diff'] > 0) & (df['prev_macd_diff'] <= 0)
df['cross_down'] = (df['macd_diff'] < 0) & (df['prev_macd_diff'] >= 0)

print(f"\n手动计算的MACD交叉:")
print(f"  上穿次数: {df['cross_up'].sum()}")
print(f"  下穿次数: {df['cross_down'].sum()}")

print(f"\n策略记录的price_cross:")
print(f"  非零次数: {(df['price_cross'] != 0).sum()}")
print(f"  正值次数: {(df['price_cross'] > 0).sum()}")
print(f"  负值次数: {(df['price_cross'] < 0).sum()}")

# 显示几个交叉点
if df['cross_up'].any():
    print("\n前5个上穿点:")
    cross_points = df[df['cross_up']][['datetime', 'price_macd', 'price_macd_signal', 'price_cross']].head(5)
    print(cross_points.to_string())

print("\n" + "=" * 80)
print("Volume MACD 统计")
print("=" * 80)
print(df[['volume_macd', 'volume_macd_signal', 'volume_cross']].describe())

print("\n" + "=" * 80)
print("HLBW 统计")
print("=" * 80)
print(df[['hlbw_trend', 'hlbw_macd', 'hlbw_macd_signal', 'hlbw_cross']].describe())

print("\n" + "=" * 80)
print("Prophet 统计")
print("=" * 80)
print(df[['prophet_yhat', 'prophet_phase', 'prophet_duration', 'prophet_cross']].describe())

print("\n" + "=" * 80)
print("Phase 分布")
print("=" * 80)
print(f"Price XLPL Phase:")
print(df['price_xlpl_phase'].value_counts().sort_index())
print(f"\nVolume XLPL Phase:")
print(df['volume_xlpl_phase'].value_counts().sort_index())
print(f"\nHLBW XLPL Phase:")
print(df['hlbw_xlpl_phase'].value_counts().sort_index())
print(f"\nProphet Phase:")
print(df['prophet_phase'].value_counts().sort_index())

print("\n" + "=" * 80)
print("信号统计")
print("=" * 80)
print(f"做多入场信号: {(df['long_entry_signal'] > 0).sum()} 次")
print(f"做空入场信号: {(df['short_entry_signal'] < 0).sum()} 次")
print(f"做多出场信号: {df['long_exit_signal'].sum()} 次")
print(f"做空出场信号: {df['short_exit_signal'].sum()} 次")

# 保存分析结果
output_file = debug_dir / f"analysis_{latest_csv.stem}.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("调试数据分析报告\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"数据文件: {latest_csv}\n")
    f.write(f"总记录数: {len(df)}\n")
    f.write(f"时间范围: {df['datetime'].iloc[0]} 至 {df['datetime'].iloc[-1]}\n\n")
    
    f.write("手动计算的MACD交叉:\n")
    f.write(f"  上穿次数: {df['cross_up'].sum()}\n")
    f.write(f"  下穿次数: {df['cross_down'].sum()}\n\n")
    
    f.write("策略记录的price_cross:\n")
    f.write(f"  非零次数: {(df['price_cross'] != 0).sum()}\n\n")

print(f"\n分析报告已保存: {output_file}")

