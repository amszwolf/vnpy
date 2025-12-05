"""
加仓策略系统使用演示 (Scaling Strategy Demo)

展示如何使用加仓策略系统进行自定义测试和分析。

Python环境：aidata311
"""

import sys
from datetime import datetime

from trading_signal_database_manager import TradingSignalDatabaseManager
from scaling_strategy import (
    ScalingConfig, 
    generate_scaling_signals,
    calculate_scaling_performance,
    SCALING_CONFIGS
)
from test_scaling_strategies import (
    test_single_strategy,
    compare_all_strategies,
    generate_comparison_report
)


def demo_1_test_single_strategy():
    """演示1: 测试单个策略"""
    print("\n" + "="*70)
    print("演示1: 测试单个策略")
    print("="*70)
    
    # 使用金字塔策略测试螺纹钢
    result = test_single_strategy(
        ticker='RB.SHF',
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy_name='pyramid',
        config=SCALING_CONFIGS['pyramid']
    )
    
    if result['status'] == 'success':
        metrics = result['metrics']
        print(f"\n✓ 测试成功！")
        print(f"  品种: {result['ticker']}")
        print(f"  策略: {result['strategy']}")
        print(f"  总收益率: {metrics['total_return_pct']:.2f}%")
        print(f"  夏普比率: {metrics['sharpe_ratio']:.4f}")
        print(f"  胜率: {metrics['win_rate']:.2%}")
        print(f"  最大回撤: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  交易次数: {metrics['total_trades']}")
    else:
        print(f"\n❌ 测试失败: {result.get('status')}")


def demo_2_custom_strategy():
    """演示2: 创建和测试自定义策略"""
    print("\n" + "="*70)
    print("演示2: 创建和测试自定义策略")
    print("="*70)
    
    # 定义自定义策略：更激进的加仓方式
    custom_config = ScalingConfig(
        scaling_method='custom_aggressive',
        max_position=10,
        scaling_sequence=[6, 3, 1],  # 超激进：首次6手
        add_position_condition='price_move',
        add_position_threshold=0.003,  # 更小的阈值，更频繁加仓
        use_trailing_stop=True,
        trailing_stop_pct=0.025  # 2.5%移动止损
    )
    
    print(f"\n自定义策略配置:")
    print(f"  加仓序列: {custom_config.scaling_sequence}")
    print(f"  加仓条件: {custom_config.add_position_condition}")
    print(f"  加仓阈值: {custom_config.add_position_threshold*100}%")
    print(f"  移动止损: {custom_config.trailing_stop_pct*100}%")
    
    # 测试自定义策略
    result = test_single_strategy(
        ticker='RB.SHF',
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy_name='custom_aggressive',
        config=custom_config
    )
    
    if result['status'] == 'success':
        metrics = result['metrics']
        print(f"\n✓ 自定义策略测试结果:")
        print(f"  总收益率: {metrics['total_return_pct']:.2f}%")
        print(f"  夏普比率: {metrics['sharpe_ratio']:.4f}")
        print(f"  胜率: {metrics['win_rate']:.2%}")
        print(f"  交易次数: {metrics['total_trades']}")


def demo_3_compare_strategies():
    """演示3: 对比多个策略"""
    print("\n" + "="*70)
    print("演示3: 对比多个策略")
    print("="*70)
    
    # 选择要对比的策略
    test_strategies = {
        'pyramid': SCALING_CONFIGS['pyramid'],
        'linear': SCALING_CONFIGS['linear'],
        'aggressive_pyramid': SCALING_CONFIGS['aggressive_pyramid']
    }
    
    print(f"\n对比策略: {list(test_strategies.keys())}")
    print(f"测试品种: RB.SHF")
    print(f"测试周期: 2025-01-01 至 2025-01-31")
    
    # 运行对比测试
    results = compare_all_strategies(
        tickers=['RB.SHF'],
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategies=test_strategies,
        parallel=False  # 串行运行便于观察
    )
    
    # 显示对比结果
    print("\n对比结果:")
    print("-" * 70)
    print(f"{'策略':<20} {'收益率':>10} {'夏普比率':>10} {'胜率':>8} {'交易次数':>8}")
    print("-" * 70)
    
    for strategy_name, result in results['RB.SHF'].items():
        if result['status'] == 'success':
            m = result['metrics']
            print(f"{strategy_name:<20} {m['total_return_pct']:>9.2f}% "
                  f"{m['sharpe_ratio']:>10.4f} {m['win_rate']:>7.2%} "
                  f"{m['total_trades']:>8d}")


def demo_4_strategy_optimization():
    """演示4: 策略参数优化"""
    print("\n" + "="*70)
    print("演示4: 策略参数优化")
    print("="*70)
    
    # 测试不同的加仓阈值
    thresholds = [0.003, 0.005, 0.008, 0.010]
    
    print(f"\n优化目标: 找出最佳加仓阈值")
    print(f"测试阈值: {[f'{t*100}%' for t in thresholds]}")
    print(f"基础策略: pyramid")
    
    best_sharpe = 0
    best_threshold = 0
    
    print("\n测试结果:")
    print("-" * 60)
    print(f"{'阈值':>6} {'收益率':>10} {'夏普比率':>10} {'胜率':>8}")
    print("-" * 60)
    
    for threshold in thresholds:
        # 创建配置
        config = ScalingConfig(
            scaling_method='pyramid',
            max_position=10,
            scaling_sequence=[4, 3, 2, 1],
            add_position_condition='price_move',
            add_position_threshold=threshold,
            use_trailing_stop=True,
            trailing_stop_pct=0.02
        )
        
        # 测试
        result = test_single_strategy(
            ticker='RB.SHF',
            start_date='2025-01-01',
            end_date='2025-01-31',
            strategy_name=f'pyramid_{threshold}',
            config=config
        )
        
        if result['status'] == 'success':
            m = result['metrics']
            print(f"{threshold*100:>5.1f}% {m['total_return_pct']:>9.2f}% "
                  f"{m['sharpe_ratio']:>10.4f} {m['win_rate']:>7.2%}")
            
            if m['sharpe_ratio'] > best_sharpe:
                best_sharpe = m['sharpe_ratio']
                best_threshold = threshold
    
    print("-" * 60)
    print(f"\n✓ 最佳阈值: {best_threshold*100}% (夏普比率: {best_sharpe:.4f})")


def demo_5_performance_analysis():
    """演示5: 性能指标详细分析"""
    print("\n" + "="*70)
    print("演示5: 性能指标详细分析")
    print("="*70)
    
    # 测试一个策略并详细分析
    result = test_single_strategy(
        ticker='RB.SHF',
        start_date='2025-01-01',
        end_date='2025-01-31',
        strategy_name='pyramid',
        config=SCALING_CONFIGS['pyramid']
    )
    
    if result['status'] != 'success':
        print("❌ 测试失败")
        return
    
    m = result['metrics']
    
    print("\n📊 完整性能报告")
    print("="*70)
    
    print("\n【收益指标】")
    print(f"  初始资金: ${m['initial_capital']:,.2f}")
    print(f"  最终资金: ${m['final_capital']:,.2f}")
    print(f"  总收益: ${m['total_return']:,.2f} ({m['total_return_pct']:.2f}%)")
    print(f"  年化收益: ${m['annual_return']:,.2f} ({m['annual_return_pct']:.2f}%)")
    
    print("\n【风险指标】")
    print(f"  夏普比率: {m['sharpe_ratio']:.4f}")
    print(f"  最大回撤: ${m['max_drawdown']:,.2f} ({m['max_drawdown_pct']:.2f}%)")
    
    print("\n【交易统计】")
    print(f"  总交易次数: {m['total_trades']}")
    print(f"  盈利交易: {m['winning_trades']} ({m['win_rate']:.2%})")
    print(f"  亏损交易: {m['losing_trades']} ({(1-m['win_rate']):.2%})")
    
    print("\n【盈亏分析】")
    print(f"  盈亏比: {m['profit_factor']:.2f}")
    print(f"  平均每笔: ${m['avg_trade']:.2f}")
    print(f"  平均盈利: ${m['avg_win']:.2f}")
    print(f"  平均亏损: ${m['avg_loss']:.2f}")
    
    print("\n【加仓分析】")
    print(f"  平均加仓层级: {m['avg_scaling_levels']:.2f}")
    print(f"  测试天数: {m['trading_days']}")
    
    print("\n【综合评价】")
    if m['sharpe_ratio'] > 2.0:
        rating = "⭐⭐⭐⭐⭐ 优秀"
    elif m['sharpe_ratio'] > 1.5:
        rating = "⭐⭐⭐⭐ 良好"
    elif m['sharpe_ratio'] > 1.0:
        rating = "⭐⭐⭐ 合格"
    else:
        rating = "⭐⭐ 需改进"
    
    print(f"  综合评级: {rating}")


def main():
    """主函数：运行所有演示"""
    print("\n" + "="*70)
    print("加仓策略系统使用演示")
    print("="*70)
    print("\n本演示将展示以下功能:")
    print("  1. 测试单个策略")
    print("  2. 创建和测试自定义策略")
    print("  3. 对比多个策略")
    print("  4. 策略参数优化")
    print("  5. 性能指标详细分析")
    
    input("\n按回车键开始演示...")
    
    # 运行所有演示
    demo_1_test_single_strategy()
    input("\n按回车键继续...")
    
    demo_2_custom_strategy()
    input("\n按回车键继续...")
    
    demo_3_compare_strategies()
    input("\n按回车键继续...")
    
    demo_4_strategy_optimization()
    input("\n按回车键继续...")
    
    demo_5_performance_analysis()
    
    print("\n" + "="*70)
    print("演示完成！")
    print("="*70)
    print("\n💡 提示:")
    print("  - 查看 SCALING_STRATEGY_README.md 了解快速开始")
    print("  - 查看 加仓策略系统使用指南.md 了解详细用法")
    print("  - 运行 python test_scaling_strategies.py 进行完整测试")
    print("  - 运行 测试加仓策略.bat 快速测试")
    print("\n")


if __name__ == "__main__":
    main()

