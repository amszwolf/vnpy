# -*- coding: utf-8 -*-
"""
Bar生成器（简化版）

VNPy的BarGenerator已经提供了1分钟→5分钟的转换功能
本模块作为扩展，提供额外的Bar合成工具

当前版本：占位符，使用VNPy内置的BarGenerator
"""

from vnpy.trader.utility import BarGenerator as VNPyBarGenerator
from vnpy.trader.object import BarData


class Bar5MinGenerator(VNPyBarGenerator):
    """
    5分钟Bar生成器
    
    继承自VNPy的BarGenerator，专门用于1分钟→5分钟转换
    """
    
    def __init__(self, on_bar_callback, on_5min_bar_callback):
        """
        初始化5分钟Bar生成器
        
        Parameters:
        -----------
        on_bar_callback : callable
            1分钟Bar回调函数
        on_5min_bar_callback : callable
            5分钟Bar回调函数
        """
        # 调用父类构造函数
        # window=5 表示每5个1分钟Bar合成一个5分钟Bar
        super().__init__(
            on_bar=on_bar_callback,
            window=5,
            on_window_bar=on_5min_bar_callback
        )
    
    def update_bar(self, bar: BarData):
        """
        更新Bar数据
        
        Parameters:
        -----------
        bar : BarData
            1分钟Bar数据
        """
        super().update_bar(bar)


def create_5min_bar_generator(on_1min_bar, on_5min_bar):
    """
    创建5分钟Bar生成器的工厂函数
    
    Parameters:
    -----------
    on_1min_bar : callable
        1分钟Bar回调函数
    on_5min_bar : callable
        5分钟Bar回调函数
        
    Returns:
    --------
    Bar5MinGenerator : Bar生成器实例
    """
    return Bar5MinGenerator(on_1min_bar, on_5min_bar)


# ====================================================================
# 测试代码
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Bar生成器测试")
    print("=" * 60)
    print("\n功能说明:")
    print("  - 使用 VNPy 内置的 BarGenerator")
    print("  - 支持 1分钟 → 5分钟 Bar合成")
    print("  - 在 HLM5Strategy 中已集成使用")
    print("\n使用示例:")
    print("```python")
    print("from vnpy.trader.utility import BarGenerator")
    print("")
    print("# 在策略的__init__中")
    print("self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)")
    print("")
    print("# 在策略的on_bar中")
    print("self.bg.update_bar(bar)")
    print("```")
    print("=" * 60)

