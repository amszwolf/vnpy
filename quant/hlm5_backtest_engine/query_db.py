# -*- coding: utf-8 -*-
"""查询数据库记录"""

import sqlite3

conn = sqlite3.connect('trading_signals.db')
cursor = conn.cursor()

print("=" * 60)
print("数据库记录查询")
print("=" * 60)

# 查询backtest_summary
cursor.execute("SELECT COUNT(*) FROM backtest_summary")
bt_count = cursor.fetchone()[0]
print(f"\nbacktest_summary: {bt_count} 条记录")

if bt_count > 0:
    cursor.execute("""
        SELECT strategy_id, ticker, strategy_name, sharpe_ratio, total_trades, status
        FROM backtest_summary
        ORDER BY created_at DESC
        LIMIT 3
    """)
    print("\n  最新记录:")
    for row in cursor.fetchall():
        print(f"    - {row[0]}")
        print(f"      {row[2]} | {row[1]} | 夏普:{row[3]:.2f} | 交易:{row[4]} | {row[5]}")

# 查询optimal_strategies
cursor.execute("SELECT COUNT(*) FROM optimal_strategies")
opt_count = cursor.fetchone()[0]
print(f"\noptimal_strategies: {opt_count} 条记录")

if opt_count > 0:
    cursor.execute("""
        SELECT strategy_id, ticker, strategy_name, sharpe_ratio, status
        FROM optimal_strategies
        ORDER BY sharpe_ratio DESC
        LIMIT 3
    """)
    print("\n  Top 3 (按夏普比率):")
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"    {i}. {row[0]}")
        print(f"       {row[2]} | {row[1]} | 夏普:{row[3]:.2f} | {row[4]}")

conn.close()

print("\n" + "=" * 60)

