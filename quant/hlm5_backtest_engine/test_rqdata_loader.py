# -*- coding: utf-8 -*-
"""
测试RQData加载器
"""

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from rqdata_loader import load_futures_data_from_rqdata


def test_load_data():
    """测试加载数据"""
    
    print("=" * 80)
    print("测试RQData加载器")
    print("=" * 80)
    
    # 测试加载OI.ZCE的数据（仅5天）
    df = load_futures_data_from_rqdata(
        ticker='OI.ZCE',
        start_date='2025-01-02',
        end_date='2025-01-10',
        interval='5m'
    )
    
    if df.empty:
        print("\n❌ 数据加载失败")
        return False
    
    print(f"\n✅ 数据加载成功")
    print(f"\n数据样本（前5行）:")
    print(df.head())
    
    print(f"\n数据统计:")
    print(df.describe())
    
    return True


if __name__ == "__main__":
    success = test_load_data()
    
    if success:
        print("\n" + "=" * 80)
        print("✅ RQData加载器测试通过")
        print("=" * 80)
        print("\n下一步: 运行完整回测")
        print("  python test_rqdata_backtest.py")
    else:
        print("\n" + "=" * 80)
        print("❌ RQData加载器测试失败")
        print("=" * 80)

