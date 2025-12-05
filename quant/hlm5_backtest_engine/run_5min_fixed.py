"""
测试5分钟数据 + aggressive_pyramid加仓策略（串行处理）
Python环境：aidata311
"""

import os
import webbrowser
import time

# 清理数据库
if os.path.exists('trading_signals.db'):
    os.remove('trading_signals.db')
    print("✓ 已删除旧数据库")

print("\n" + "="*70)
print("🚀 开始测试：5分钟数据 + aggressive_pyramid策略")
print("="*70)
print("  时间段: 2025-01-01 至 2025-06-30 (6个月)")
print("  数据表: tb_futures_rboi_5min")
print("  品种数: 2")
print("  处理方式: 串行")
print("="*70 + "\n")

# 重命名1分钟的图表
if os.path.exists('output'):
    for file in os.listdir('output'):
        if file.endswith('.html'):
            old_path = os.path.join('output', file)
            new_path = os.path.join('output', f'1min_{file}')
            try:
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(old_path, new_path)
                print(f"  重命名: {file} -> 1min_{file}")
            except:
                pass

# 导入hlm5模块
from hlm5_all_parallel import main, EQUITY_CONFIG

# 禁用并行处理
EQUITY_CONFIG['PARALLEL_PROCESSING'] = False

# 直接调用main函数
try:
    main(
        update_mode='smart',
        enable_realtime=False,
        max_tickers=2,
        verbose=True,
        start_date='2025-01-01',
        end_date='2025-06-30',
        raw_db='tushare',
        raw_table='tb_futures_rboi_5min',
        scaling_strategy='aggressive_pyramid'
    )
    
    print("\n" + "="*70)
    print("✅ 5分钟数据测试完成!")
    print("="*70)
    print("\n📊 生成的文件:")
    print("  - trading_signals.db (数据库)")
    print("  - output/RB.SHF_analysis.html (螺纹钢图表 - 5分钟)")
    print("  - output/OI.ZCE_analysis.html (菜籽油图表 - 5分钟)")
    print("  - output/1min_*.html (1分钟数据图表)")
    
    # 重命名5分钟的图表
    print("\n  重命名5分钟图表...")
    if os.path.exists('output'):
        for file in os.listdir('output'):
            if file.endswith('.html') and not file.startswith('1min_'):
                old_path = os.path.join('output', file)
                new_path = os.path.join('output', f'5min_{file}')
                try:
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(old_path, new_path)
                    print(f"    重命名: {file} -> 5min_{file}")
                except Exception as e:
                    print(f"    ✗ 重命名失败: {e}")
    
    # 打开所有图表
    print("\n🌐 正在打开所有图表...")
    
    all_charts = []
    if os.path.exists('output'):
        for file in sorted(os.listdir('output')):
            if file.endswith('.html'):
                all_charts.append(os.path.join('output', file))
    
    for chart in all_charts:
        try:
            abs_path = os.path.abspath(chart)
            webbrowser.open(f'file:///{abs_path}')
            print(f"  ✓ {os.path.basename(chart)}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ✗ 无法打开 {chart}: {e}")
    
    print(f"\n✅ 已打开 {len(all_charts)} 个图表")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

