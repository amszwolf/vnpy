"""
运行加仓策略回测并生成可视化曲线
Python环境：aidata311
"""

from demo_scaling_usage import demo_5_performance_analysis
from test_scaling_strategies import compare_all_strategies, generate_comparison_report
from scaling_strategy_visualizer import visualize_all_strategies
from scaling_strategy import SCALING_CONFIGS
import webbrowser
import os
import time

def run_backtest_and_visualize():
    """运行回测并生成可视化图表"""
    print("\n" + "="*70)
    print("🚀 开始运行加仓策略回测")
    print("="*70)
    
    # 测试参数
    tickers = ['RB.SHF', 'OI.ZCE']
    start_date = '2025-01-01'
    end_date = '2025-01-31'
    
    # 选择要测试的策略
    strategies = {
        'pyramid': SCALING_CONFIGS['pyramid'],
        'aggressive_pyramid': SCALING_CONFIGS['aggressive_pyramid'],
        'linear': SCALING_CONFIGS['linear']
    }
    
    print(f"\n📊 测试配置:")
    print(f"  品种: {tickers}")
    print(f"  周期: {start_date} 至 {end_date}")
    print(f"  策略: {list(strategies.keys())}")
    print(f"  数据库: trading_signals.db")
    
    # 运行对比测试
    print("\n⏳ 正在运行回测...")
    results = compare_all_strategies(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        strategies=strategies,
        db_path='trading_signals.db',
        parallel=False  # 串行执行便于观察
    )
    
    # 生成文字报告
    print("\n📝 生成对比报告...")
    report = generate_comparison_report(results)
    
    # 生成可视化图表
    print("\n📈 生成可视化图表...")
    chart_files = visualize_all_strategies(results, output_dir='output')
    
    print("\n" + "="*70)
    print("✅ 回测完成！")
    print("="*70)
    
    # 打印结果摘要
    print("\n📊 回测结果摘要:")
    print("-"*70)
    
    for ticker, strategies_result in results.items():
        print(f"\n【{ticker}】")
        for strategy_name, result in strategies_result.items():
            if result['status'] == 'success':
                m = result['metrics']
                print(f"  {strategy_name:20s}: "
                      f"收益 {m['total_return_pct']:7.2f}%, "
                      f"夏普 {m['sharpe_ratio']:6.4f}, "
                      f"胜率 {m['win_rate']:6.2%}, "
                      f"回撤 {m['max_drawdown_pct']:6.2f}%, "
                      f"交易 {m['total_trades']:3d}次")
    
    # 显示生成的图表文件
    print("\n📁 生成的图表文件:")
    print("-"*70)
    for ticker, files in chart_files.items():
        print(f"\n{ticker}:")
        for file_path in files:
            print(f"  📄 {os.path.basename(file_path)}")
    
    # 自动打开图表
    print("\n🌐 正在浏览器中打开图表...")
    print("-"*70)
    
    opened_charts = []
    for ticker, files in chart_files.items():
        for file_path in files:
            try:
                abs_path = os.path.abspath(file_path)
                print(f"  ✓ 打开: {os.path.basename(file_path)}")
                webbrowser.open(f'file:///{abs_path}')
                opened_charts.append(file_path)
                time.sleep(0.8)  # 给浏览器时间加载
            except Exception as e:
                print(f"  ✗ 无法打开 {file_path}: {e}")
    
    if opened_charts:
        print(f"\n✅ 已在浏览器中打开 {len(opened_charts)} 个图表")
    
    print("\n" + "="*70)
    print("💡 提示:")
    print("  - 图表保存在 output/ 目录")
    print("  - Bokeh图表支持交互操作（缩放、平移、十字线等）")
    print("  - 可以对比不同策略的收益曲线和加仓行为")
    print("="*70)

if __name__ == "__main__":
    run_backtest_and_visualize()

