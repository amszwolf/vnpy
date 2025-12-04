"""
参数优化工具
支持遗传算法和网格搜索优化
"""

from datetime import datetime
import sys
from pathlib import Path

from vnpy.trader.optimize import OptimizationSetting

# 添加路径
examples_dir = Path(__file__).parent.parent
sys.path.insert(0, str(examples_dir))
sys.path.insert(0, str(examples_dir / "strategies"))
sys.path.insert(0, str(examples_dir / "backtesting"))

from vnpy_ctastrategy.backtesting import BacktestingEngine
from strategies.ma_cross_strategy import MaCrossStrategy


def run_optimization():
    """
    运行参数优化
    """
    print("=" * 60)
    print("策略参数优化")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
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
    engine.add_strategy(MaCrossStrategy, {})
    
    # 设置优化参数
    setting = OptimizationSetting()
    
    # 设置优化目标（可选：sharpe_ratio, total_return, max_dd等）
    setting.set_target("sharpe_ratio")
    
    # 添加优化参数
    # 格式：参数名, 最小值, 最大值, 步长
    setting.add_parameter("fast_window", 5, 20, 5)      # 快速均线周期：5-20，步长5
    setting.add_parameter("slow_window", 20, 50, 10)   # 慢速均线周期：20-50，步长10
    setting.add_parameter("sl_percent", 0.01, 0.05, 0.01)  # 止损百分比：1%-5%，步长1%
    setting.add_parameter("tp_percent", 0.02, 0.08, 0.02)  # 止盈百分比：2%-8%，步长2%
    
    # 运行遗传算法优化
    print("\n开始运行遗传算法优化...")
    print("这可能需要一些时间，请耐心等待...")
    
    engine.run_ga_optimization(setting)
    
    print("\n优化完成！")
    print("请查看优化结果，选择最优参数组合")


if __name__ == "__main__":
    run_optimization()

