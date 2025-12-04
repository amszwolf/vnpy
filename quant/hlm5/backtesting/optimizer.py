# -*- coding: utf-8 -*-
"""
HLM5 策略参数优化

使用遗传算法优化策略参数
基于 VNPy 的 OptimizationSetting
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.optimize import OptimizationSetting

# 导入策略
from strategies.hlm5_strategy import HLM5Strategy

# 导入配置
from hlm5_config import EQUITY_CONFIG
from futures_config import FUTURES_CONFIG, get_contract_specs


def run_optimization(
    symbol='OI888',
    exchange=Exchange.CZCE,
    start_date=None,
    end_date=None,
    interval='5m',
    capital=100000,
    target='sharpe_ratio'  # 优化目标
):
    """
    运行参数优化
    
    Parameters:
    -----------
    symbol : str
        合约代码
    exchange : Exchange
        交易所
    start_date : datetime
        回测起始日期
    end_date : datetime
        回测结束日期
    interval : str
        回测周期
    capital : float
        初始资金
    target : str
        优化目标指标
        
    Returns:
    --------
    list : 优化结果列表
    """
    print("=" * 60)
    print("HLM5 策略参数优化")
    print("=" * 60)
    
    # 1. 设置默认参数
    if start_date is None:
        start_date_str = FUTURES_CONFIG['BACKTEST_CONFIG']['start_date']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    if end_date is None:
        end_date = datetime.now()
    
    # 2. 获取合约规格
    specs = get_contract_specs(symbol)
    
    print(f"\n优化配置:")
    print(f"  合约: {symbol}.{exchange.value}")
    print(f"  时间: {start_date.date()} 至 {end_date.date()}")
    print(f"  周期: {interval}")
    print(f"  初始资金: {capital:,.0f} 元")
    print(f"  优化目标: {target}")
    
    # 3. 创建回测引擎
    engine = BacktestingEngine()
    
    # 4. 设置回测参数
    engine.set_parameters(
        vt_symbol=f"{symbol}.{exchange.value}",
        interval=Interval(interval),
        start=start_date,
        end=end_date,
        rate=specs['commission']['open_ratio'],
        slippage=specs['slippage']['fixed_slippage'],
        size=specs['multiplier'],
        pricetick=specs['pricetick'],
        capital=capital
    )
    
    # 5. 添加策略
    strategy_setting = {}
    engine.add_strategy(HLM5Strategy, strategy_setting)
    
    # 6. 定义优化参数范围
    print("\n定义优化参数范围...")
    
    setting = OptimizationSetting()
    
    # Price MACD 参数优化
    setting.add_parameter("price_macd_long", 15, 25, 5)    # 15, 20, 25
    setting.add_parameter("price_macd_mid", 6, 10, 2)      # 6, 8, 10
    setting.add_parameter("price_macd_short", 3, 7, 2)     # 3, 5, 7
    
    # Volume MACD 参数优化
    setting.add_parameter("volume_macd_long", 15, 25, 5)   # 15, 20, 25
    setting.add_parameter("volume_macd_mid", 6, 10, 2)     # 6, 8, 10
    setting.add_parameter("volume_macd_short", 3, 7, 2)    # 3, 5, 7
    
    # HLBW 参数优化
    setting.add_parameter("hlbw_lookback", 30, 50, 10)     # 30, 40, 50
    setting.add_parameter("hlbw_inner_ema", 2, 4, 1)       # 2, 3, 4
    
    # 风险控制参数优化
    setting.add_parameter("stop_loss_pct", 0.02, 0.06, 0.02)    # 2%, 4%, 6%
    setting.add_parameter("take_profit_pct", 0.08, 0.16, 0.04)  # 8%, 12%, 16%
    
    # 设置优化目标
    setting.set_target(target)
    
    # 7. 运行优化
    print("\n" + "=" * 60)
    print("开始参数优化...")
    print("=" * 60)
    print(f"优化方法: 遗传算法")
    print(f"种群大小: {setting.population_size if hasattr(setting, 'population_size') else '默认'}")
    print(f"最大代数: {setting.max_generation if hasattr(setting, 'max_generation') else '默认'}")
    print("\n这可能需要较长时间，请耐心等待...")
    
    try:
        # 运行遗传算法优化
        results = engine.run_ga_optimization(
            setting, 
            population_size=20,  # 种群大小
            ngen=10,             # 最大代数
            output=True          # 输出优化过程
        )
        
        if not results:
            print("\n✗ 优化未返回结果")
            return None
        
        # 8. 分析优化结果
        print("\n" + "=" * 60)
        print("优化结果")
        print("=" * 60)
        
        # 按目标指标排序
        results = sorted(
            results,
            key=lambda x: x[1],
            reverse=True
        )
        
        # 显示前10组最佳参数
        print(f"\n前10组最佳参数（按 {target} 排序）:")
        print("-" * 60)
        
        for i, (params, target_value, stats) in enumerate(results[:10], 1):
            print(f"\n第 {i} 名: {target} = {target_value:.4f}")
            print(f"  参数:")
            for key, value in params.items():
                print(f"    {key}: {value}")
            
            # 显示关键指标
            if stats:
                print(f"  统计:")
                print(f"    总收益率: {stats.get('total_return', 0)*100:.2f}%")
                print(f"    最大回撤: {stats.get('max_ddpercent', 0)*100:.2f}%")
                print(f"    夏普比率: {stats.get('sharpe_ratio', 0):.3f}")
                print(f"    总交易次数: {stats.get('total_trade_count', 0)}")
        
        # 9. 保存结果
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("HLM5 策略参数优化结果\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"合约: {symbol}\n")
            f.write(f"优化目标: {target}\n")
            f.write(f"回测周期: {interval}\n\n")
            
            for i, (params, target_value, stats) in enumerate(results[:10], 1):
                f.write(f"\n第 {i} 名:\n")
                f.write(f"  {target}: {target_value:.4f}\n")
                f.write(f"  参数: {params}\n")
                if stats:
                    f.write(f"  统计: {stats}\n")
        
        print(f"\n优化结果已保存到: {output_file}")
        
        print("\n" + "=" * 60)
        print("✅ 参数优化完成！")
        print("=" * 60)
        
        # 10. 推荐最佳参数
        if results:
            best_params, best_value, best_stats = results[0]
            print(f"\n🎯 推荐使用以下参数（{target} = {best_value:.4f}）:")
            print("-" * 60)
            for key, value in best_params.items():
                print(f"  {key} = {value}")
            print("-" * 60)
            print("\n提示：将这些参数更新到 hlm5_config.py 中")
        
        return results
        
    except Exception as e:
        print(f"\n✗ 优化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def quick_optimization():
    """
    快速优化 - 使用默认配置
    """
    results = run_optimization(
        symbol='OI888',
        exchange=Exchange.CZCE,
        interval='5m',
        capital=100000,
        target='sharpe_ratio'
    )
    
    return results


# ====================================================================
# 主程序
# ====================================================================

def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HLM5 策略参数优化')
    parser.add_argument('--symbol', type=str, default='OI888', help='合约代码')
    parser.add_argument('--start', type=str, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000, help='初始资金')
    parser.add_argument('--interval', type=str, default='5m', help='回测周期')
    parser.add_argument('--target', type=str, default='sharpe_ratio',
                       help='优化目标 (sharpe_ratio, total_return, etc.)')
    
    args = parser.parse_args()
    
    # 解析日期
    start_date = None
    if args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    
    end_date = None
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    
    # 运行优化
    results = run_optimization(
        symbol=args.symbol,
        exchange=Exchange.CZCE,
        start_date=start_date,
        end_date=end_date,
        interval=args.interval,
        capital=args.capital,
        target=args.target
    )


if __name__ == "__main__":
    # 如果没有命令行参数，运行快速优化
    if len(sys.argv) == 1:
        print("\n使用默认配置运行快速优化...")
        print("提示：使用 --help 查看所有参数选项\n")
        quick_optimization()
    else:
        main()

