# -*- coding: utf-8 -*-
"""验证实盘数据库结构"""

import sqlite3
from pathlib import Path


def verify_live_database():
    """验证实盘数据库表结构"""
    print("=" * 80)
    print("实盘数据库结构验证")
    print("=" * 80)
    
    db_path = "trading_signals.db"
    
    if not Path(db_path).exists():
        print(f"\n❌ 数据库不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 检查所有表
    print("\n[1/4] 检查表结构...")
    
    expected_tables = [
        'trading_data',
        'live_strategies', 
        'live_trades',
        'live_performance_daily'
    ]
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in expected_tables:
        if table in tables:
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} - 缺失")
    
    # 2. 检查字段
    print("\n[2/4] 检查live_strategies表字段...")
    cursor.execute("PRAGMA table_info(live_strategies)")
    columns = cursor.fetchall()
    
    key_columns = ['strategy_id', 'ticker', 'prophet_model', 'prophet_params', 
                   'indicator_params', 'trading_params', 'full_config']
    
    column_names = [col[1] for col in columns]
    for col in key_columns:
        if col in column_names:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} - 缺失")
    
    # 3. 检查索引
    print("\n[3/4] 检查索引...")
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master 
        WHERE type='index' AND name LIKE 'idx_%'
    """)
    idx_count = cursor.fetchone()[0]
    print(f"  ✅ 创建了 {idx_count} 个索引")
    
    # 4. 检查与回测引擎的兼容性
    print("\n[4/4] 检查与回测引擎的兼容性...")
    
    backtest_db = Path("../../hlm5_backtest_engine/trading_signals.db")
    if backtest_db.exists():
        backtest_conn = sqlite3.connect(backtest_db)
        backtest_cursor = backtest_conn.cursor()
        
        # 查询optimal_strategies
        backtest_cursor.execute("""
            SELECT strategy_id, ticker, sharpe_ratio, LENGTH(prophet_model) as model_size
            FROM optimal_strategies
        """)
        strategies = backtest_cursor.fetchall()
        
        if strategies:
            print(f"  ✅ 找到 {len(strategies)} 个可导入的最优策略")
            for sid, ticker, sharpe, model_size in strategies:
                model_info = f"Prophet: {model_size/1024:.2f} KB" if model_size else "无Prophet"
                print(f"    - {sid[:30]}... | {ticker} | 夏普{sharpe:.2f} | {model_info}")
        else:
            print("  ⚠️  回测引擎中没有最优策略")
        
        backtest_conn.close()
    else:
        print(f"  ⚠️  回测引擎数据库不存在: {backtest_db}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ 验证完成！")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    verify_live_database()

