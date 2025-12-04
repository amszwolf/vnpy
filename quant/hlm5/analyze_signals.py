# -*- coding: utf-8 -*-
"""
分析交易信号类型
"""

import pandas as pd
from pathlib import Path

# 读取最新的调试CSV
debug_dir = Path("output/debug")
csv_files = list(debug_dir.glob("debug_data_*.csv"))
latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)

print(f"分析文件: {latest_csv}")
print("=" * 80)

df = pd.read_csv(latest_csv)

# 分析入场信号
long_entries = df[df['long_entry_signal'] > 0]
short_entries = df[df['short_entry_signal'] < 0]

print(f"\n做多入场信号分析:")
print(f"  总计: {len(long_entries)} 次")
if len(long_entries) > 0:
    print(f"\n  信号类型分布:")
    signal_counts = long_entries['long_entry_signal'].value_counts().sort_index()
    for signal_type, count in signal_counts.items():
        signal_names = {
            1: "price_cross & volume_cross & hlbw_cross",
            2: "price_cross & volume_la & hlbw_cross",
            3: "price_cross & volume_xi & hlbw_cross",
            4: "volume_la & volume_cross & hlbw_cross",
            5: "price_cross & volume_cross & hlbw_la",
            6: "兜底信号(cross_count>=2 或 special_case)"
        }
        print(f"    类型{signal_type} ({signal_names.get(signal_type, '未知')}): {count} 次")
    
    print(f"\n  前5个做多入场信号:")
    print(long_entries[['datetime', 'close', 'long_entry_signal', 'price_cross', 
                        'volume_cross', 'hlbw_cross']].head().to_string(index=False))

print(f"\n做空入场信号分析:")
print(f"  总计: {len(short_entries)} 次")
if len(short_entries) > 0:
    print(f"\n  信号类型分布:")
    signal_counts = short_entries['short_entry_signal'].value_counts().sort_index()
    for signal_type, count in signal_counts.items():
        signal_names = {
            -1: "price_cross & volume_cross & hlbw_cross",
            -2: "price_cross & volume_la & hlbw_cross",
            -3: "price_cross & volume_xi & hlbw_cross",
            -4: "volume_la & volume_cross & hlbw_cross",
            -5: "price_cross & volume_cross & hlbw_lo",
            -6: "兜底信号(cross_count>=2 或 special_case)"
        }
        print(f"    类型{signal_type} ({signal_names.get(signal_type, '未知')}): {count} 次")
    
    print(f"\n  前5个做空入场信号:")
    print(short_entries[['datetime', 'close', 'short_entry_signal', 'price_cross', 
                         'volume_cross', 'hlbw_cross']].head().to_string(index=False))

# 分析Cross信号的联合出现
print(f"\n\nCross信号联合分析:")
print(f"  Price & Volume & HLBW 三个都有Cross信号: {len(df[(df['price_cross'] != 0) & (df['volume_cross'] != 0) & (df['hlbw_cross'] != 0)])} 次")
print(f"  至少两个Cross信号: {len(df[((df['price_cross'] != 0) & (df['volume_cross'] != 0)) | ((df['price_cross'] != 0) & (df['hlbw_cross'] != 0)) | ((df['volume_cross'] != 0) & (df['hlbw_cross'] != 0))])} 次")
print(f"  只有一个Cross信号: {len(df[(df['price_cross'] != 0) ^ (df['volume_cross'] != 0) ^ (df['hlbw_cross'] != 0)])} 次")

