"""
策略回测运行脚本
"""

from datetime import datetime
import sys
from pathlib import Path

# 添加策略目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "strategies"))

import sys
from pathlib import Path

# 添加路径
examples_dir = Path(__file__).parent.parent
sys.path.insert(0, str(examples_dir))
sys.path.insert(0, str(examples_dir / "strategies"))
sys.path.insert(0, str(examples_dir / "backtesting"))

from backtesting.backtest_engine import QuantBacktestEngine
from strategies.ma_cross_strategy import MaCrossStrategy


def main():
    """
    运行回测示例
    """
    print("=" * 60)
    print("策略回测示例")
    print("=" * 60)
    
    # 创建回测引擎
    engine = QuantBacktestEngine()
    
    # 设置回测参数
    engine.set_parameters(
        vt_symbol="IF888.CFFEX",  # 股指期货主力合约（使用888表示主力合约）
        interval="1m",             # 1分钟K线（策略内部会合成5分钟K线）
        start=datetime(2023, 1, 1),
        end=datetime(2023, 12, 31),
        rate=0.3/10000,            # 手续费率：万0.3
        slippage=0.2,              # 滑点：0.2点
        size=300,                  # 合约乘数：300
        pricetick=0.2,             # 价格跳动：0.2点
        capital=1_000_000          # 初始资金：100万
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
    
    # 显示图表
    print("\n显示回测图表...")
    engine.show_chart()
    
    # 保存结果（可选）
    # engine.save_result("backtest_result.csv")


if __name__ == "__main__":
    main()

