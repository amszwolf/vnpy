"""
完整的量化交易工作流示例
从策略开发、回测、优化到模拟交易和实盘交易的完整流程
"""

from datetime import datetime
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / "strategies"))
sys.path.insert(0, str(Path(__file__).parent / "backtesting"))
sys.path.insert(0, str(Path(__file__).parent / "analysis"))

from backtesting.backtest_engine import QuantBacktestEngine
from strategies.ma_cross_strategy import MaCrossStrategy
from analysis.performance_analyzer import PerformanceAnalyzer
from analysis.review_analyzer import ReviewAnalyzer


def step1_backtest():
    """
    步骤1: 策略回测
    """
    print("=" * 60)
    print("步骤1: 策略回测")
    print("=" * 60)
    
    # 创建回测引擎
    engine = QuantBacktestEngine()
    
    # 设置回测参数
    engine.set_parameters(
        vt_symbol="IF888.CFFEX",
        interval="1m",  # 1分钟K线（策略内部会合成5分钟K线）
        start=datetime(2023, 1, 1),
        end=datetime(2023, 12, 31),
        rate=0.3/10000,
        slippage=0.2,
        size=300,
        pricetick=0.2,
        capital=1_000_000
    )
    
    # 添加策略
    strategy_setting = {
        "fast_window": 10,
        "slow_window": 30,
        "fixed_size": 1,
        "sl_percent": 0.02,
        "tp_percent": 0.04
    }
    engine.add_strategy(MaCrossStrategy, strategy_setting)
    
    # 运行回测
    print("\n开始运行回测...")
    result_df = engine.run_backtest()
    
    # 打印统计指标
    print("\n回测完成！")
    engine.print_statistics()
    
    # 保存结果
    engine.save_result("backtest_result.csv")
    
    return result_df


def step2_analyze(result_df):
    """
    步骤2: 绩效分析
    """
    print("\n" + "=" * 60)
    print("步骤2: 绩效分析")
    print("=" * 60)
    
    # 创建分析器
    analyzer = PerformanceAnalyzer(result_df)
    
    # 计算统计指标
    analyzer.calculate_statistics()
    
    # 打印统计指标
    analyzer.print_statistics()
    
    # 导出报告
    analyzer.export_report("performance_report.txt")
    
    return analyzer


def step3_review(result_df):
    """
    步骤3: 复盘分析
    """
    print("\n" + "=" * 60)
    print("步骤3: 复盘分析")
    print("=" * 60)
    
    # 创建复盘分析器
    reviewer = ReviewAnalyzer(result_df)
    
    # 分析交易
    trade_df = reviewer.analyze_trades()
    if not trade_df.empty:
        print(f"\n交易分析:")
        print(f"总交易次数: {len(trade_df)}")
        print(f"盈利交易: {(trade_df['is_win']).sum()}")
        print(f"亏损交易: {(~trade_df['is_win']).sum()}")
        print(f"最大单笔盈利: {trade_df['profit'].max():.2f}")
        print(f"最大单笔亏损: {trade_df['profit'].min():.2f}")
    
    # 分析时间段
    periods = reviewer.analyze_periods()
    if periods:
        print(f"\n时间段表现:")
        print(f"最佳月份: {periods.get('best_month')}")
        print(f"最差月份: {periods.get('worst_month')}")
    
    # 找出问题
    problems = reviewer.find_problems()
    if problems:
        print(f"\n发现的问题:")
        for i, problem in enumerate(problems, 1):
            print(f"{i}. {problem}")
    else:
        print("\n未发现明显问题")
    
    # 生成复盘报告
    reviewer.generate_review_report("review_report.txt")
    
    return reviewer


def main():
    """
    主函数：完整的量化交易工作流
    """
    print("=" * 60)
    print("VeighNa 量化交易完整工作流")
    print("=" * 60)
    print("\n本示例展示完整的量化交易流程：")
    print("1. 策略回测")
    print("2. 绩效分析")
    print("3. 复盘分析")
    print("\n提示：")
    print("- 回测完成后，如果结果满意，可以进行参数优化")
    print("- 优化后再次回测验证")
    print("- 通过模拟交易验证策略")
    print("- 最后进行实盘交易")
    print("\n" + "=" * 60)
    
    # 步骤1: 回测
    result_df = step1_backtest()
    
    # 步骤2: 分析
    analyzer = step2_analyze(result_df)
    
    # 步骤3: 复盘
    reviewer = step3_review(result_df)
    
    print("\n" + "=" * 60)
    print("完整工作流执行完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 如果回测结果不满意，修改策略或参数")
    print("2. 如果回测结果满意，运行参数优化：")
    print("   python backtesting/optimizer.py")
    print("3. 优化后运行模拟交易：")
    print("   python trading/paper_trading.py")
    print("4. 模拟交易验证后运行实盘交易：")
    print("   python trading/live_trading.py")


if __name__ == "__main__":
    main()

