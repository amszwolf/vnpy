"""
测试1分钟数据 + aggressive_pyramid加仓策略（禁用并行处理）
Python环境：aidata311
"""

import os
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
print("  处理方式: 串行（禁用并行处理）")
print("="*70 + "\n")

# 导入hlm5模块
import hlm5_all_parallel

# 修改配置：禁用并行处理
hlm5_all_parallel.EQUITY_CONFIG['PARALLEL_PROCESSING'] = False

# 直接调用main函数
try:
    hlm5_all_parallel.main(
        update_mode='smart',
        enable_realtime=False,
        max_tickers=2,
        verbose=True,
        start_date='2025-01-01',
        end_date='2025-01-31',
        raw_db='tushare',
        raw_table='tb_futures_rboi_1min',
        scaling_strategy='aggressive_pyramid'
    )
    
    print("\n" + "="*70)
    print("✅ 1分钟数据测试完成!")
    print("="*70)
    print("\n📊 生成的文件:")
    print("  - trading_signals.db (数据库)")
    print("  - output/RB.SHF_analysis.html (螺纹钢图表)")
    print("  - output/OI.ZCE_analysis.html (菜籽油图表)")
    
    # 打开图表
    print("\n🌐 正在打开图表...")
    import webbrowser
    import time
    
    charts = [
        'output/RB.SHF_analysis.html',
        'output/OI.ZCE_analysis.html'
    ]
    
    for chart in charts:
        if os.path.exists(chart):
            abs_path = os.path.abspath(chart)
            webbrowser.open(f'file:///{abs_path}')
            print(f"  ✓ {chart}")
            time.sleep(0.5)
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

