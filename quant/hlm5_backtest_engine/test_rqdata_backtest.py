# -*- coding: utf-8 -*-
"""
测试使用RQData的回测
"""

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from run_integrated_backtest import run_integrated_backtest_with_charts


def test_rqdata_backtest():
    """测试RQData数据源的回测"""
    
    print("=" * 80)
    print("测试RQData回测引擎")
    print("=" * 80)
    
    # 运行1个月的回测
    run_integrated_backtest_with_charts(
        ticker='OI.ZCE',
        start_date='2025-01-01',
        end_date='2025-02-01',
        scaling_strategy='aggressive_pyramid',
        my_raw_db='rqdata',  # 不再使用，但保留参数兼容性
        my_raw_table='rqdata',  # 不再使用，但保留参数兼容性
        db_path='trading_signals.db',  # 使用根目录的数据库
        generate_charts=True,
        auto_save=True,
        auto_promote=True,
        sharpe_threshold=2.0
    )


if __name__ == "__main__":
    test_rqdata_backtest()

