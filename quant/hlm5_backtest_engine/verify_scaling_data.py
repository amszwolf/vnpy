"""
验证加仓策略数据是否成功保存到数据库

Python环境：aidata311
"""

import sqlite3
import pandas as pd

def verify_scaling_data(db_path='trading_signals.db', ticker='RB.SHF'):
    """验证加仓策略数据"""
    
    conn = sqlite3.connect(db_path)
    
    # 查询加仓策略数据
    query = """
    SELECT datetime, close, 
           Entry_Signal, Position,
           Scaling_Signal, Scaling_Position, Scaling_Level, Scaling_Strategy
    FROM trading_data 
    WHERE ticker = ? 
      AND Scaling_Strategy IS NOT NULL
    ORDER BY datetime
    LIMIT 20
    """
    
    df = pd.read_sql(query, conn, params=[ticker])
    
    print(f"=" * 80)
    print(f"验证加仓策略数据 - {ticker}")
    print(f"=" * 80)
    
    if df.empty:
        print("❌ 未找到加仓策略数据！")
        return
    
    print(f"\n✓ 找到 {len(df)} 条加仓策略记录（显示前20条）\n")
    print(df.to_string(index=False))
    
    # 统计信息
    query2 = """
    SELECT 
        Scaling_Strategy,
        COUNT(*) as total_records,
        SUM(CASE WHEN Scaling_Signal = 1 THEN 1 ELSE 0 END) as entry_count,
        SUM(CASE WHEN Scaling_Signal > 1 THEN 1 ELSE 0 END) as add_count,
        SUM(CASE WHEN Scaling_Signal = -1 THEN 1 ELSE 0 END) as exit_count,
        MAX(Scaling_Position) as max_position,
        MAX(Scaling_Level) as max_level
    FROM trading_data 
    WHERE ticker = ? AND Scaling_Strategy IS NOT NULL
    GROUP BY Scaling_Strategy
    """
    
    stats_df = pd.read_sql(query2, conn, params=[ticker])
    
    print(f"\n" + "=" * 80)
    print("加仓策略统计信息")
    print("=" * 80)
    print(stats_df.to_string(index=False))
    
    conn.close()
    
    print(f"\n✓ 数据验证完成！")

if __name__ == "__main__":
    verify_scaling_data()

