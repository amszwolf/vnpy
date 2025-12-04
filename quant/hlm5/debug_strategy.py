# -*- coding: utf-8 -*-
"""
快速调试脚本 - 检查策略为何没有交易信号
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval, Exchange

from strategies.hlm5_strategy import HLM5Strategy
from futures_config import get_contract_specs

def quick_debug():
    """快速调试回测"""
    
    print("="*60)
    print("HLM5 策略快速调试")
    print("="*60)
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 获取合约规格
    specs = get_contract_specs('OI888')
    
    # 设置回测参数 - 只回测1天
    engine.set_parameters(
        vt_symbol="OI888.CZCE",
        interval=Interval.MINUTE,  # 使用1分钟数据
        start=datetime(2025, 1, 2),
        end=datetime(2025, 1, 3),
        rate=specs['commission']['open_ratio'],
        slippage=specs['slippage']['fixed_slippage'],
        size=specs['multiplier'],
        pricetick=specs['pricetick'],
        capital=100000
    )
    
    # 添加策略 - 启用调试模式
    strategy_setting = {
        'debug_mode': True,
        'fixed_size': 1
    }
    
    engine.add_strategy(HLM5Strategy, strategy_setting)
    
    print("\n加载数据...")
    engine.load_data()
    print(f"✓ 数据加载完成")
    
    print("\n运行回测...")
    engine.run_backtesting()
    print(f"✓ 回测完成")
    
    # 获取策略实例
    strategy = engine.strategy
    
    # 检查调试数据
    if hasattr(strategy, 'debug_data'):
        print(f"\n调试数据收集情况:")
        print(f"  - debug_data存在: ✓")
        print(f"  - debug_data长度: {len(strategy.debug_data)}")
        
        if strategy.debug_data:
            print(f"\n第一条数据样本:")
            first_record = strategy.debug_data[0]
            for key, value in list(first_record.items())[:10]:
                print(f"  {key}: {value}")
        else:
            print(f"  ⚠️ debug_data为空！")
            
            # 检查可能的原因
            print(f"\n可能的原因:")
            print(f"  - ArrayManager大小: {strategy.am.size}")
            print(f"  - ArrayManager已初始化: {strategy.am.inited}")
            print(f"  - BarGenerator已创建: {strategy.bg is not None}")
            
            if hasattr(strategy, '_bar_count'):
                print(f"  - on_5min_bar被调用次数: {strategy._bar_count}")
            else:
                print(f"  - on_5min_bar可能从未被调用")
    else:
        print(f"\n✗ 策略没有debug_data属性")
        print(f"  debug_mode: {strategy.debug_mode}")
    
    print("\n" + "="*60)
    print("调试完成")
    print("="*60)

if __name__ == "__main__":
    quick_debug()

