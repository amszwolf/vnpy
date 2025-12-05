#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
5分钟数据加仓策略测试 - 确保图表生成和显示
"""
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# 确保输出目录存在
output_dir = Path('output')
output_dir.mkdir(exist_ok=True)

print("="*80)
print("5分钟数据加仓策略测试")
print("="*80)
print(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"输出目录: {output_dir.absolute()}")
print("="*80)

# 导入必要的模块
from trading_signal_database_manager import TradingSignalDatabaseManager
from scaling_strategy import (
    generate_scaling_signals,
    calculate_scaling_performance,
    SCALING_CONFIGS
)
from scaling_strategy_visualizer import ScalingStrategyVisualizer

# 测试参数
tickers = ['RB.SHF', 'OI.ZCE']
start_date = '2025-01-01'
end_date = '2025-06-30'
db_path = 'trading_signals.db'

print(f"\n测试参数:")
print(f"  品种: {', '.join(tickers)}")
print(f"  时间: {start_date} 至 {end_date}")
print(f"  数据库: {db_path}")
print(f"  策略数量: {len(SCALING_CONFIGS)}")
print()

# 存储结果
all_results = {}
chart_files = []

# 测试每个品种
for ticker_idx, ticker in enumerate(tickers, 1):
    print(f"\n{'='*80}")
    print(f"[{ticker_idx}/{len(tickers)}] 测试 {ticker}")
    print(f"{'='*80}")
    
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path)
    
    ticker_results = {}
    ticker_signals = {}
    
    # 测试每个策略
    for strategy_idx, (strategy_name, config) in enumerate(SCALING_CONFIGS.items(), 1):
        print(f"\n  [{strategy_idx}/{len(SCALING_CONFIGS)}] 策略: {strategy_name}")
        
        try:
            # 生成加仓信号
            print(f"      生成信号...")
            signals_df = generate_scaling_signals(db, ticker, start_date, end_date, config)
            
            if signals_df.empty:
                print(f"      ❌ 无信号数据")
                ticker_results[strategy_name] = {
                    'status': 'no_data',
                    'metrics': {}
                }
                continue
            
            # 计算性能指标
            print(f"      计算性能...")
            metrics = calculate_scaling_performance(signals_df)
            
            # 保存结果
            ticker_results[strategy_name] = {
                'status': 'success',
                'metrics': metrics
            }
            ticker_signals[strategy_name] = signals_df
            
            # 显示关键指标
            print(f"      ✓ 总收益: {metrics['total_return_pct']:.2f}%")
            print(f"      ✓ 胜率: {metrics['win_rate']:.2%}")
            print(f"      ✓ 交易次数: {metrics['total_trades']}")
            print(f"      ✓ 平均加仓层级: {metrics['avg_scaling_levels']:.2f}")
            
            if metrics['avg_scaling_levels'] == 0:
                print(f"      ⚠️ 警告：未触发加仓！")
            
        except Exception as e:
            print(f"      ❌ 错误: {str(e)}")
            ticker_results[strategy_name] = {
                'status': 'error',
                'metrics': {},
                'error': str(e)
            }
    
    # 关闭数据库
    db.close()
    
    # 保存品种结果
    all_results[ticker] = ticker_results
    
    # 生成图表
    if ticker_signals:
        print(f"\n  生成 {ticker} 的可视化图表...")
        
        try:
            visualizer = ScalingStrategyVisualizer(output_dir=str(output_dir))
            
            # 为每个成功的策略生成详细图表
            for strategy_name, signals_df in ticker_signals.items():
                if not signals_df.empty:
                    print(f"    生成 {strategy_name} 详细图表...")
                    
                    chart_file = visualizer.create_strategy_chart(
                        signals_df=signals_df,
                        strategy_name=strategy_name,
                        ticker=ticker,
                        metrics=ticker_results[strategy_name]['metrics']
                    )
                    
                    if chart_file:
                        chart_files.append(chart_file)
                        print(f"      ✓ {os.path.basename(chart_file)}")
            
            # 生成策略对比图表
            if len(ticker_signals) > 1:
                print(f"    生成策略对比图表...")
                
                comparison_file = visualizer.create_comparison_chart(
                    all_signals=ticker_signals,
                    all_metrics={k: v['metrics'] for k, v in ticker_results.items() if v['status'] == 'success'},
                    ticker=ticker
                )
                
                if comparison_file:
                    chart_files.append(comparison_file)
                    print(f"      ✓ {os.path.basename(comparison_file)}")
            
        except Exception as e:
            print(f"    ❌ 图表生成错误: {str(e)}")
            import traceback
            traceback.print_exc()

print(f"\n{'='*80}")
print("测试完成！")
print(f"{'='*80}")

# 生成报告摘要
print(f"\n测试结果摘要:")
print(f"{'='*80}")

for ticker, strategies in all_results.items():
    print(f"\n{ticker}:")
    
    successful = [s for s, r in strategies.items() if r['status'] == 'success']
    
    if successful:
        # 找出最佳策略（按夏普比率）
        best_strategy = max(
            successful,
            key=lambda s: strategies[s]['metrics'].get('sharpe_ratio', float('-inf'))
        )
        
        best_metrics = strategies[best_strategy]['metrics']
        
        print(f"  ✓ 成功测试 {len(successful)} 个策略")
        print(f"  ✓ 最佳策略: {best_strategy}")
        print(f"    - 总收益: {best_metrics['total_return_pct']:.2f}%")
        print(f"    - 夏普比率: {best_metrics['sharpe_ratio']:.4f}")
        print(f"    - 胜率: {best_metrics['win_rate']:.2%}")
        print(f"    - 平均加仓层级: {best_metrics['avg_scaling_levels']:.2f}")
        
        # 显示所有策略
        print(f"\n  所有策略表现:")
        for strategy_name in successful:
            m = strategies[strategy_name]['metrics']
            print(f"    {strategy_name:20s}: 收益 {m['total_return_pct']:7.2f}%, "
                  f"夏普 {m['sharpe_ratio']:6.4f}, 层级 {m['avg_scaling_levels']:.2f}")
    else:
        print(f"  ❌ 无成功策略")

# 显示生成的图表文件
print(f"\n{'='*80}")
print(f"生成的图表文件 ({len(chart_files)} 个):")
print(f"{'='*80}")

if chart_files:
    for chart_file in chart_files:
        print(f"  ✓ {chart_file}")
    
    # 保存图表列表到文件
    list_file = output_dir / 'chart_files_list.txt'
    with open(list_file, 'w', encoding='utf-8') as f:
        f.write("生成的图表文件列表\n")
        f.write("="*80 + "\n\n")
        for chart_file in chart_files:
            f.write(f"{chart_file}\n")
    
    print(f"\n图表列表已保存到: {list_file}")
else:
    print("  ⚠️ 未生成图表文件")

# 打开关键图表
print(f"\n{'='*80}")
print("打开图表...")
print(f"{'='*80}")

# 找出对比图表
comparison_charts = [f for f in chart_files if 'comparison' in f.lower()]
detail_charts = [f for f in chart_files if 'comparison' not in f.lower()]

charts_to_open = []

# 先打开对比图表（最重要）
if comparison_charts:
    charts_to_open.extend(comparison_charts)
    print(f"\n对比图表 ({len(comparison_charts)} 个):")
    for chart in comparison_charts:
        print(f"  {os.path.basename(chart)}")

# 再打开前2个详细图表（示例）
if detail_charts:
    charts_to_open.extend(detail_charts[:2])
    print(f"\n详细图表示例 (显示前2个):")
    for chart in detail_charts[:2]:
        print(f"  {os.path.basename(chart)}")
    
    if len(detail_charts) > 2:
        print(f"\n  (还有 {len(detail_charts)-2} 个详细图表未自动打开)")
        print(f"  请在 output/ 目录中手动查看")

print()

# 尝试在浏览器中打开图表
opened_count = 0
for chart_file in charts_to_open:
    try:
        abs_path = os.path.abspath(chart_file)
        print(f"打开: {os.path.basename(chart_file)}")
        webbrowser.open(f'file:///{abs_path}')
        opened_count += 1
        time.sleep(0.5)  # 避免同时打开太多
    except Exception as e:
        print(f"  ⚠️ 自动打开失败: {e}")
        print(f"  请手动打开: {chart_file}")

if opened_count > 0:
    print(f"\n✓ 成功在浏览器中打开 {opened_count} 个图表")
else:
    print(f"\n⚠️ 自动打开失败，请手动打开图表")
    print(f"图表位置: {output_dir.absolute()}")

# 打开output目录
print(f"\n打开output目录...")
try:
    os.startfile(str(output_dir.absolute()))
    print(f"✓ 已打开目录")
except Exception as e:
    print(f"⚠️ 无法打开目录: {e}")

print(f"\n{'='*80}")
print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*80}")
print(f"\n所有图表文件都保存在: {output_dir.absolute()}")
print(f"如果浏览器没有自动打开，请手动打开上述目录中的HTML文件")
print()

