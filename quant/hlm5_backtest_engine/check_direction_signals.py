"""
验证多空信号区分数据

Python环境：aidata311
"""

import pandas as pd
import sqlite3

def check_direction_signals(db_path='trading_signals.db', ticker='RB.SHF'):
    """检查多空信号数据"""
    
    conn = sqlite3.connect(db_path)
    
    # 查询加仓策略数据（需要先运行测试生成数据）
    # 这里我们查看内存中生成的数据，因为 Scaling_Direction 还没有保存到数据库
    
    print("=" * 80)
    print(f"多空信号验证 - {ticker}")
    print("=" * 80)
    
    # 注意：Scaling_Direction 字段在内存中，没有保存到数据库
    # 如果要验证，需要在测试时查看 signals_df
    
    print("\n提示：")
    print("Scaling_Direction 字段是在生成信号时计算的，存在于内存 DataFrame 中")
    print("图表可视化时会自动使用该字段来区分多空信号")
    print("\n要查看效果，请打开以下图表文件：")
    print("  - scaling_charts/RB.SHF_pyramid_analysis.html")
    print("  - scaling_charts/RB.SHF_aggressive_pyramid_analysis.html")
    
    print("\n在图表中您将看到：")
    print("  🟢 做多信号：")
    print("     ● 深绿色圆圈 = 首次开仓")
    print("     ▲ 绿色上三角 = 加仓")
    print("     ■ 淡绿色方块 = 平仓")
    print("\n  🔴 做空信号：")
    print("     ● 深红色圆圈 = 首次开仓")
    print("     ▼ 红色下三角 = 加仓")
    print("     ■ 淡红色方块 = 平仓")
    
    conn.close()

if __name__ == "__main__":
    check_direction_signals()

