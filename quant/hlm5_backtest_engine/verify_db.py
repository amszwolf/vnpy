# -*- coding: utf-8 -*-
"""快速验证数据库表结构"""

import sqlite3

conn = sqlite3.connect('trading_signals.db')
cursor = conn.cursor()

print("=" * 60)
print("数据库表结构验证")
print("=" * 60)

# 查询所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print(f"\n共有 {len(tables)} 个表:")
for table in tables:
    table_name = table[0]
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print(f"\n✓ {table_name} ({len(columns)} 列)")
    
    # 显示前5列
    for i, col in enumerate(columns[:5], 1):
        col_name = col[1]
        col_type = col[2]
        print(f"    {i}. {col_name} ({col_type})")
    
    if len(columns) > 5:
        print(f"    ... 还有 {len(columns) - 5} 列")

# 查询索引
cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name")
indexes = cursor.fetchall()

print(f"\n共有 {len(indexes)} 个索引:")
for idx in indexes:
    print(f"  ✓ {idx[0]} (on {idx[1]})")

conn.close()

print("\n" + "=" * 60)
print("验证完成！")
print("=" * 60)

