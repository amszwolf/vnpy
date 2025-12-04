# -*- coding: utf-8 -*-
"""
测试indicators模块的Cross信号计算
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

# 导入indicators模块
from utils.indicators import calculate_macd_signals, merge_price_cross_signals

print("=" * 80)
print("测试Indicators模块 - Cross信号计算")
print("=" * 80)

# 1. 从调试CSV加载数据
csv_path = Path("output/debug/debug_data_OI888_20251204_180231.csv")
if not csv_path.exists():
    print("❌ 调试CSV文件不存在！")
    exit(1)

df = pd.read_csv(csv_path)
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

print(f"\n加载数据: {len(df)} 条K线")
print(f"数据时间范围: {df.index[0]} 至 {df.index[-1]}")

# 2. 测试Price MACD
print("\n" + "=" * 80)
print("测试 Price MACD 计算")
print("=" * 80)

price_config = {
    'macd_long': 20,
    'macd_mid': 8,
    'macd_short': 5,
    'diff_ema_period': 2
}

price_signals = calculate_macd_signals(df['close'], config=price_config)

print(f"\n返回的列: {price_signals.columns.tolist()}")
print(f"数据长度: {len(price_signals)}")

# 检查Cross_1信号
cross_1_nonzero = (price_signals['Cross_1'] != 0).sum()
cross_1_up = (price_signals['Cross_1'] > 0).sum()
cross_1_down = (price_signals['Cross_1'] < 0).sum()

print(f"\n===  Cross_1 原始信号 ===")
print(f"  非零次数: {cross_1_nonzero}")
print(f"  上穿(>0): {cross_1_up}")
print(f"  下穿(<0): {cross_1_down}")

# 显示前10个非零Cross_1
if cross_1_nonzero > 0:
    cross_points = price_signals[price_signals['Cross_1'] != 0].head(10)
    print(f"\n前10个Cross_1信号:")
    print(cross_points[['MACD', 'MACD_Signal', 'Cross_1']].to_string())
else:
    print("\n⚠️ Cross_1全部为0！")
    
    # 手动计算验证
    print("\n手动验证MACD交叉:")
    dif = price_signals['MACD']
    dea = price_signals['MACD_Signal']
    
    # 检查NaN
    print(f"  DIF包含NaN: {dif.isna().sum()} 个")
    print(f"  DEA包含NaN: {dea.isna().sum()} 个")
    
    # 手动计算交叉
    manual_cross = []
    for i in range(1, len(dif)):
        if not pd.isna(dif.iloc[i]) and not pd.isna(dea.iloc[i]) and \
           not pd.isna(dif.iloc[i-1]) and not pd.isna(dea.iloc[i-1]):
            if dif.iloc[i] > dea.iloc[i] and dif.iloc[i-1] <= dea.iloc[i-1]:
                manual_cross.append((i, 'UP', dif.iloc[i], dea.iloc[i]))
            elif dif.iloc[i] < dea.iloc[i] and dif.iloc[i-1] >= dea.iloc[i-1]:
                manual_cross.append((i, 'DN', dif.iloc[i], dea.iloc[i]))
    
    print(f"  手动计算交叉次数: {len(manual_cross)}")
    if manual_cross:
        print(f"\n  前5个交叉点:")
        for idx, direction, dif_val, dea_val in manual_cross[:5]:
            print(f"    位置{idx}: {direction}, DIF={dif_val:.4f}, DEA={dea_val:.4f}")
            print(f"      Cross_1[{idx}]={price_signals['Cross_1'].iloc[idx]}, Cross_1[{idx-1}]={price_signals['Cross_1'].iloc[idx-1]}")

# 3. 测试merge_price_cross_signals
print("\n" + "=" * 80)
print("测试 merge_price_cross_signals")
print("=" * 80)

merged_cross = merge_price_cross_signals(price_signals)
merged_nonzero = (merged_cross != 0).sum()

print(f"合并后的Cross信号:")
print(f"  非零次数: {merged_nonzero}")
print(f"  数据类型: {type(merged_cross)}")
print(f"  长度: {len(merged_cross)}")

if merged_nonzero > 0:
    # 找到非零位置
    nonzero_idx = np.where(merged_cross != 0)[0]
    print(f"\n前10个非零位置: {nonzero_idx[:10]}")
    print(f"对应的值: {merged_cross[nonzero_idx[:10]]}")
else:
    print("\n⚠️ 合并后的Cross信号全部为0！")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)

