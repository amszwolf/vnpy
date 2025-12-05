#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的加仓策略测试 - 确保图表输出
"""
import os
import sys
import webbrowser
import time
from datetime import datetime

print("="*80)
print("加仓策略测试 - 5分钟数据")
print("="*80)
print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 导入模块
print("导入模块...")
from trading_signal_database_manager import TradingSignalDatabaseManager
from scaling_strategy import generate_scaling_signals, calculate_scaling_performance, SCALING_CONFIGS
from scaling_strategy_visualizer import visualize_all_strategies

# 创建output目录
os.makedirs('output', exist_ok=True)
print(f"输出目录: {os.path.abspath('output')}\n")

# 测试参数
tickers = ['RB.SHF', 'OI.ZCE']
start_date = '2025-01-01'
end_date = '2025-06-30'

print(f"测试参数:")
print(f"  品种: {', '.join(tickers)}")
print(f"  时间: {start_date} 至 {end_date}")
print(f"  策略: {', '.join(SCALING_CONFIGS.keys())}\n")

# 存储结果
all_results = {}

# 对每个品种进行测试
for ticker in tickers:
    print(f"\n{'='*80}")
    print(f"测试品种: {ticker}")
    print(f"{'='*80}")
    
    db = TradingSignalDatabaseManager('trading_signals.db')
    ticker_results = {}
    
    for strategy_name, config in SCALING_CONFIGS.items():
        print(f"\n  策略: {strategy_name}")
        
        try:
            # 生成信号
            signals_df = generate_scaling_signals(db, ticker, start_date, end_date, config)
            
            if signals_df.empty:
                print(f"    ❌ 无信号数据")
                ticker_results[strategy_name] = {'status': 'no_data', 'metrics': {}}
                continue
            
            # 计算性能
            metrics = calculate_scaling_performance(signals_df)
            
            print(f"    ✓ 收益: {metrics['total_return_pct']:.2f}%")
            print(f"    ✓ 胜率: {metrics['win_rate']:.2%}")
            print(f"    ✓ 交易: {metrics['total_trades']}")
            print(f"    ✓ 层级: {metrics['avg_scaling_levels']:.2f}")
            
            ticker_results[strategy_name] = {
                'status': 'success',
                'metrics': metrics,
                'signals_df': signals_df
            }
            
        except Exception as e:
            print(f"    ❌ 错误: {str(e)}")
            ticker_results[strategy_name] = {'status': 'error', 'metrics': {}}
    
    db.close()
    all_results[ticker] = ticker_results

print(f"\n{'='*80}")
print("生成图表...")
print(f"{'='*80}\n")

# 生成图表
chart_files = visualize_all_strategies(all_results, output_dir='output')

# 显示生成的文件
print(f"\n生成的图表:")
all_charts = []
for ticker, files in chart_files.items():
    print(f"\n{ticker}:")
    for file_path in files:
        print(f"  ✓ {file_path}")
        all_charts.append(file_path)

# 打开对比图表
print(f"\n{'='*80}")
print("打开图表...")
print(f"{'='*80}\n")

comparison_charts = [f for f in all_charts if 'comparison' in f.lower()]

if comparison_charts:
    for chart in comparison_charts:
        try:
            abs_path = os.path.abspath(chart)
            print(f"打开: {chart}")
            webbrowser.open(f'file:///{abs_path}')
            time.sleep(1)
        except Exception as e:
            print(f"  错误: {e}")
else:
    print("未找到对比图表")

# 打开第一个详细图表（示例）
detail_charts = [f for f in all_charts if 'comparison' not in f.lower()]
if detail_charts:
    try:
        chart = detail_charts[0]
        abs_path = os.path.abspath(chart)
        print(f"打开: {chart}")
        webbrowser.open(f'file:///{abs_path}')
    except Exception as e:
        print(f"  错误: {e}")

# 打开output目录
print(f"\n打开output目录...")
try:
    os.startfile('output')
    print("✓ 目录已打开")
except Exception as e:
    print(f"  错误: {e}")

print(f"\n{'='*80}")
print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*80}")
print(f"\n所有图表保存在: {os.path.abspath('output')}")
print("如果浏览器未自动打开，请手动打开上述目录中的HTML文件\n")

