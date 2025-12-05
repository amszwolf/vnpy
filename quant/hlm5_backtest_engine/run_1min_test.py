"""
测试1分钟数据 + aggressive_pyramid加仓策略
Python环境：aidata311
"""

import os
import subprocess
import sys

# 清理数据库
if os.path.exists('trading_signals.db'):
    os.remove('trading_signals.db')
    print("✓ 已删除旧数据库")

print("\n" + "="*70)
print("🚀 开始测试：1分钟数据 + aggressive_pyramid策略")
print("="*70)
print("  时间段: 2025-01-01 至 2025-01-31 (1个月)")
print("  数据表: tb_futures_rboi_1min")
print("  品种数: 2")
print("="*70 + "\n")

# 直接调用主模块
sys.argv = [
    'hlm5_all_parallel.py',
    '--raw-table', 'tb_futures_rboi_1min',
    '--start-date', '2025-01-01',
    '--end-date', '2025-01-31',
    '--scaling-strategy', 'aggressive_pyramid',
    '--max-tickers', '2',
    '--verbose'
]

# 导入并运行
try:
    import hlm5_all_parallel
    hlm5_all_parallel.main_cli()
    print("\n✅ 1分钟数据测试完成!")
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

