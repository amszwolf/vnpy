# -*- coding: utf-8 -*-
"""
HLM5 策略加仓功能测试示例

演示如何使用加仓策略
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Exchange

# 导入策略
from strategies.hlm5_strategy import HLM5Strategy

# 导入配置
from futures_config import get_contract_specs


def test_with_scaling():
    """测试启用加仓策略"""
    print("=" * 60)
    print("HLM5 策略 - 加仓模式测试")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置回测参数
    symbol = 'OI888'
    specs = get_contract_specs('OI')
    
    engine.set_parameters(
        vt_symbol=f"{symbol}.CZCE",
        interval=Interval.MINUTE_5,
        start=datetime(2025, 1, 1),
        end=datetime(2025, 1, 31),
        rate=specs['commission']['open_ratio'],
        slippage=specs['slippage']['fixed_slippage'],
        size=specs['multiplier'],
        pricetick=specs['pricetick'],
        capital=100000
    )
    
    # 策略配置：启用加仓
    strategy_setting = {
        'enable_scaling': True,              # 启用加仓
        'scaling_method': 'aggressive_pyramid',  # 激进金字塔
        'max_position': 10,                  # 最大10手
        'scaling_threshold': 0.01,           # 盈利1%后加仓
        'scaling_trailing_stop': 0.015,      # 1.5%移动止损
        'enable_bidirectional': True,
        'hold_overnight': False
    }
    
    print("\n策略配置:")
    print(f"  加仓策略: {strategy_setting['scaling_method']}")
    print(f"  最大持仓: {strategy_setting['max_position']}手")
    print(f"  加仓阈值: {strategy_setting['scaling_threshold']*100}%")
    print(f"  移动止损: {strategy_setting['scaling_trailing_stop']*100}%")
    
    # 添加策略
    engine.add_strategy(HLM5Strategy, strategy_setting)
    
    # 运行回测
    print("\n开始回测...")
    try:
        engine.load_data()
        engine.run_backtesting()
        df = engine.calculate_result()
        stats = engine.calculate_statistics()
        
        # 打印结果
        print("\n" + "=" * 60)
        print("回测结果 - 加仓模式")
        print("=" * 60)
        print(f"总收益率: {stats.get('total_return', 0)*100:.2f}%")
        print(f"夏普比率: {stats.get('sharpe_ratio', 0):.3f}")
        print(f"最大回撤: {stats.get('max_ddpercent', 0)*100:.2f}%")
        print(f"总交易次数: {stats.get('total_trade_count', 0)}")
        print(f"胜率: {stats.get('winning_trade_count', 0) / stats.get('total_trade_count', 1) * 100:.2f}%")
        print("=" * 60)
        
        return stats
    except Exception as e:
        print(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_without_scaling():
    """测试固定仓位模式（对比）"""
    print("\n\n" + "=" * 60)
    print("HLM5 策略 - 固定仓位模式测试（对比）")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置回测参数
    symbol = 'OI888'
    specs = get_contract_specs('OI')
    
    engine.set_parameters(
        vt_symbol=f"{symbol}.CZCE",
        interval=Interval.MINUTE_5,
        start=datetime(2025, 1, 1),
        end=datetime(2025, 1, 31),
        rate=specs['commission']['open_ratio'],
        slippage=specs['slippage']['fixed_slippage'],
        size=specs['multiplier'],
        pricetick=specs['pricetick'],
        capital=100000
    )
    
    # 策略配置：固定仓位
    strategy_setting = {
        'enable_scaling': False,    # 不启用加仓
        'fixed_size': 1,             # 固定1手
        'enable_bidirectional': True,
        'hold_overnight': False
    }
    
    print("\n策略配置:")
    print(f"  加仓策略: 未启用")
    print(f"  固定仓位: {strategy_setting['fixed_size']}手")
    
    # 添加策略
    engine.add_strategy(HLM5Strategy, strategy_setting)
    
    # 运行回测
    print("\n开始回测...")
    try:
        engine.load_data()
        engine.run_backtesting()
        df = engine.calculate_result()
        stats = engine.calculate_statistics()
        
        # 打印结果
        print("\n" + "=" * 60)
        print("回测结果 - 固定仓位模式")
        print("=" * 60)
        print(f"总收益率: {stats.get('total_return', 0)*100:.2f}%")
        print(f"夏普比率: {stats.get('sharpe_ratio', 0):.3f}")
        print(f"最大回撤: {stats.get('max_ddpercent', 0)*100:.2f}%")
        print(f"总交易次数: {stats.get('total_trade_count', 0)}")
        print(f"胜率: {stats.get('winning_trade_count', 0) / stats.get('total_trade_count', 1) * 100:.2f}%")
        print("=" * 60)
        
        return stats
    except Exception as e:
        print(f"回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(scaling_stats, fixed_stats):
    """对比两种模式的结果"""
    if not scaling_stats or not fixed_stats:
        print("\n无法对比：缺少回测结果")
        return
    
    print("\n\n" + "=" * 60)
    print("性能对比：加仓 vs 固定仓位")
    print("=" * 60)
    
    print(f"\n{'指标':<20} {'加仓模式':<20} {'固定仓位':<20} {'差异':<20}")
    print("-" * 80)
    
    # 总收益率
    scaling_return = scaling_stats.get('total_return', 0) * 100
    fixed_return = fixed_stats.get('total_return', 0) * 100
    diff_return = scaling_return - fixed_return
    print(f"{'总收益率':<20} {scaling_return:<20.2f}% {fixed_return:<20.2f}% {diff_return:+.2f}%")
    
    # 夏普比率
    scaling_sharpe = scaling_stats.get('sharpe_ratio', 0)
    fixed_sharpe = fixed_stats.get('sharpe_ratio', 0)
    diff_sharpe = scaling_sharpe - fixed_sharpe
    print(f"{'夏普比率':<20} {scaling_sharpe:<20.3f} {fixed_sharpe:<20.3f} {diff_sharpe:+.3f}")
    
    # 最大回撤
    scaling_dd = scaling_stats.get('max_ddpercent', 0) * 100
    fixed_dd = fixed_stats.get('max_ddpercent', 0) * 100
    diff_dd = scaling_dd - fixed_dd
    print(f"{'最大回撤':<20} {scaling_dd:<20.2f}% {fixed_dd:<20.2f}% {diff_dd:+.2f}%")
    
    # 总交易次数
    scaling_trades = scaling_stats.get('total_trade_count', 0)
    fixed_trades = fixed_stats.get('total_trade_count', 0)
    print(f"{'总交易次数':<20} {scaling_trades:<20} {fixed_trades:<20}")
    
    print("=" * 60)
    
    # 结论
    if diff_return > 0 and scaling_sharpe > fixed_sharpe:
        print("\n✅ 加仓策略表现更优：收益更高且风险调整后收益更好")
    elif diff_return > 0:
        print("\n⚠️ 加仓策略收益更高，但需注意风险控制")
    else:
        print("\n⚠️ 固定仓位表现更稳定，建议优化加仓参数")


def main():
    """主程序"""
    print("\n" + "=" * 60)
    print("HLM5 加仓策略测试")
    print("=" * 60)
    print("\n测试说明：")
    print("  - 测试1：启用加仓策略 (aggressive_pyramid)")
    print("  - 测试2：固定仓位模式 (1手)")
    print("  - 对比两种模式的性能差异")
    print("\n按 Enter 开始测试...")
    input()
    
    # 测试1：加仓模式
    scaling_stats = test_with_scaling()
    
    # 测试2：固定仓位
    fixed_stats = test_without_scaling()
    
    # 对比结果
    compare_results(scaling_stats, fixed_stats)
    
    print("\n\n测试完成！")


if __name__ == "__main__":
    main()

