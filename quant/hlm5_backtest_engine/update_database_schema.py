"""
更新数据库表结构 - 添加加仓策略字段

Python环境：aidata311
"""

import sqlite3
import os

def update_database_schema(db_path='trading_signals.db'):
    """更新数据库表结构，添加加仓策略相关字段"""
    
    print(f"正在更新数据库: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查是否已经有 Scaling_Signal 字段
    cursor.execute("PRAGMA table_info(trading_data)")
    columns = [row[1] for row in cursor.fetchall()]
    
    fields_to_add = {
        'Scaling_Signal': 'INTEGER DEFAULT 0',
        'Scaling_Position': 'INTEGER DEFAULT 0',
        'Scaling_Level': 'INTEGER DEFAULT 0',
        'Scaling_Strategy': 'TEXT'
    }
    
    for field_name, field_type in fields_to_add.items():
        if field_name not in columns:
            print(f"添加字段: {field_name} ({field_type})")
            cursor.execute(f"ALTER TABLE trading_data ADD COLUMN {field_name} {field_type}")
            print(f"✓ {field_name} 字段添加成功")
        else:
            print(f"✓ {field_name} 字段已存在，跳过")
    
    conn.commit()
    
    # 验证更新结果
    cursor.execute("PRAGMA table_info(trading_data)")
    all_columns = [row[1] for row in cursor.fetchall()]
    
    print("\n当前数据库所有字段:")
    for col in all_columns:
        print(f"  - {col}")
    
    conn.close()
    print(f"\n✓ 数据库更新完成: {db_path}")

if __name__ == "__main__":
    update_database_schema()

