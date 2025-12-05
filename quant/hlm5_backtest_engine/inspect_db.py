# -*- coding: utf-8 -*-
"""详细查看数据库状态"""

import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('trading_signals.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("数据库详细状态报告")
print("=" * 80)
print(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"数据库文件: trading_signals.db")

# ============================================================
# 1. 表结构概览
# ============================================================
print("\n" + "=" * 80)
print("1. 表结构概览")
print("=" * 80)

cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' 
    ORDER BY name
""")
tables = cursor.fetchall()

print(f"\n共有 {len(tables)} 个表:")
for table in tables:
    table_name = table['name']
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
    record_count = cursor.fetchone()['count']
    
    print(f"\n  ✓ {table_name}")
    print(f"    - 列数: {len(columns)}")
    print(f"    - 记录数: {record_count}")
    print(f"    - 列名: ", end="")
    col_names = [col['name'] for col in columns[:5]]
    print(", ".join(col_names), end="")
    if len(columns) > 5:
        print(f", ... (还有{len(columns)-5}列)", end="")
    print()

# ============================================================
# 2. 索引信息
# ============================================================
print("\n" + "=" * 80)
print("2. 索引信息")
print("=" * 80)

cursor.execute("""
    SELECT name, tbl_name, sql 
    FROM sqlite_master 
    WHERE type='index' 
    ORDER BY tbl_name, name
""")
indexes = cursor.fetchall()

print(f"\n共有 {len(indexes)} 个索引:")
current_table = None
for idx in indexes:
    if idx['tbl_name'] != current_table:
        current_table = idx['tbl_name']
        print(f"\n  {current_table}:")
    print(f"    - {idx['name']}")

# ============================================================
# 3. backtest_summary 详细信息
# ============================================================
print("\n" + "=" * 80)
print("3. backtest_summary 表详细信息")
print("=" * 80)

cursor.execute("SELECT COUNT(*) as count FROM backtest_summary")
bt_count = cursor.fetchone()['count']
print(f"\n总记录数: {bt_count}")

if bt_count > 0:
    cursor.execute("""
        SELECT 
            strategy_id, ticker, strategy_name, strategy_version,
            start_date, end_date,
            total_return, annual_return, sharpe_ratio, max_drawdown,
            win_rate, total_trades, avg_holding_period, profit_factor,
            is_optimal, status, created_at, comments
        FROM backtest_summary
        ORDER BY created_at DESC
    """)
    
    records = cursor.fetchall()
    
    for i, record in enumerate(records, 1):
        print(f"\n  记录 {i}:")
        print(f"    策略ID: {record['strategy_id']}")
        print(f"    策略名称: {record['strategy_name']} v{record['strategy_version']}")
        print(f"    合约代码: {record['ticker']}")
        print(f"    回测区间: {record['start_date']} ~ {record['end_date']}")
        print(f"    创建时间: {record['created_at']}")
        print(f"    状态: {record['status']} | 是否最优: {'是' if record['is_optimal'] else '否'}")
        print(f"\n    性能指标:")
        print(f"      - 总收益率: {record['total_return']*100:.2f}%")
        print(f"      - 年化收益: {record['annual_return']*100:.2f}%")
        print(f"      - 夏普比率: {record['sharpe_ratio']:.2f}")
        print(f"      - 最大回撤: {record['max_drawdown']*100:.2f}%")
        print(f"      - 胜率: {record['win_rate']*100:.2f}%")
        print(f"      - 总交易次数: {record['total_trades']}")
        print(f"      - 平均持仓(分钟): {record['avg_holding_period']:.1f}")
        print(f"      - 盈亏比: {record['profit_factor']:.2f}")
        
        if record['comments']:
            print(f"    备注: {record['comments']}")
    
    # 查询指标参数
    print("\n  策略配置示例 (第1条记录):")
    cursor.execute("""
        SELECT indicator_params, trading_params 
        FROM backtest_summary 
        LIMIT 1
    """)
    config = cursor.fetchone()
    
    if config['indicator_params']:
        indicators = json.loads(config['indicator_params'])
        print("\n    指标参数:")
        for ind_name, ind_config in indicators.items():
            print(f"      {ind_name}:")
            for key, value in ind_config.items():
                print(f"        - {key}: {value}")
    
    if config['trading_params']:
        trading = json.loads(config['trading_params'])
        print("\n    交易参数:")
        for key, value in trading.items():
            print(f"      - {key}: {value}")

else:
    print("\n  暂无记录")

# ============================================================
# 4. optimal_strategies 详细信息
# ============================================================
print("\n" + "=" * 80)
print("4. optimal_strategies 表详细信息")
print("=" * 80)

cursor.execute("SELECT COUNT(*) as count FROM optimal_strategies")
opt_count = cursor.fetchone()['count']
print(f"\n总记录数: {opt_count}")

if opt_count > 0:
    cursor.execute("""
        SELECT 
            strategy_id, ticker, strategy_name, strategy_version,
            start_date, end_date,
            total_return, annual_return, sharpe_ratio, max_drawdown,
            win_rate, total_trades,
            is_optimal, status, created_at, comments
        FROM optimal_strategies
        ORDER BY sharpe_ratio DESC
    """)
    
    records = cursor.fetchall()
    
    print(f"\n  Top {len(records)} 最优策略 (按夏普比率排序):")
    
    for i, record in enumerate(records, 1):
        print(f"\n  #{i} {record['strategy_id']}")
        print(f"    策略: {record['strategy_name']} v{record['strategy_version']}")
        print(f"    合约: {record['ticker']}")
        print(f"    夏普: {record['sharpe_ratio']:.2f} | "
              f"年化: {record['annual_return']*100:.2f}% | "
              f"回撤: {record['max_drawdown']*100:.2f}%")
        print(f"    交易: {record['total_trades']} | "
              f"胜率: {record['win_rate']*100:.1f}% | "
              f"状态: {record['status']}")
        print(f"    创建: {record['created_at']}")
        if record['comments']:
            print(f"    备注: {record['comments']}")

else:
    print("\n  暂无记录")

# ============================================================
# 5. 统计分析
# ============================================================
print("\n" + "=" * 80)
print("5. 统计分析")
print("=" * 80)

if bt_count > 0:
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN is_optimal = 1 THEN 1 END) as optimal_count,
            AVG(sharpe_ratio) as avg_sharpe,
            MAX(sharpe_ratio) as max_sharpe,
            MIN(sharpe_ratio) as min_sharpe,
            AVG(annual_return) as avg_return,
            AVG(win_rate) as avg_win_rate,
            SUM(total_trades) as total_trades
        FROM backtest_summary
    """)
    
    stats = cursor.fetchone()
    
    print("\n  回测统计:")
    print(f"    - 总回测次数: {stats['total']}")
    print(f"    - 最优策略数: {stats['optimal_count']}")
    print(f"    - 夏普比率: 平均 {stats['avg_sharpe']:.2f} | "
          f"最高 {stats['max_sharpe']:.2f} | "
          f"最低 {stats['min_sharpe']:.2f}")
    print(f"    - 平均年化收益: {stats['avg_return']*100:.2f}%")
    print(f"    - 平均胜率: {stats['avg_win_rate']*100:.2f}%")
    print(f"    - 累计交易次数: {stats['total_trades']}")
    
    # 按合约统计
    cursor.execute("""
        SELECT 
            ticker,
            COUNT(*) as count,
            AVG(sharpe_ratio) as avg_sharpe
        FROM backtest_summary
        GROUP BY ticker
        ORDER BY count DESC
    """)
    
    ticker_stats = cursor.fetchall()
    if len(ticker_stats) > 0:
        print("\n  按合约统计:")
        for ts in ticker_stats:
            print(f"    - {ts['ticker']}: {ts['count']}次回测, "
                  f"平均夏普 {ts['avg_sharpe']:.2f}")

else:
    print("\n  暂无统计数据")

# ============================================================
# 6. 数据库文件信息
# ============================================================
print("\n" + "=" * 80)
print("6. 数据库文件信息")
print("=" * 80)

import os
db_size = os.path.getsize('trading_signals.db')
print(f"\n  文件路径: {os.path.abspath('trading_signals.db')}")
print(f"  文件大小: {db_size:,} 字节 ({db_size/1024:.2f} KB)")

cursor.execute("PRAGMA page_count")
page_count = cursor.fetchone()[0]
cursor.execute("PRAGMA page_size")
page_size = cursor.fetchone()[0]
print(f"  页面数量: {page_count}")
print(f"  页面大小: {page_size} 字节")
print(f"  总页面大小: {page_count * page_size:,} 字节")

conn.close()

print("\n" + "=" * 80)
print("报告生成完成！")
print("=" * 80)

