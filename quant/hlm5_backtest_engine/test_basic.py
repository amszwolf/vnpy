#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import sys

# 强制UTF-8输出
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 测试数据库连接
try:
    conn = sqlite3.connect('trading_signals.db')
    cursor = conn.cursor()
    
    # 检查RB.SHF数据
    cursor.execute("""
        SELECT COUNT(*) FROM trading_data 
        WHERE ticker='RB.SHF' 
        AND datetime>='2025-01-01' 
        AND datetime<='2025-06-30'
    """)
    rb_count = cursor.fetchone()[0]
    
    # 检查OI.ZCE数据
    cursor.execute("""
        SELECT COUNT(*) FROM trading_data 
        WHERE ticker='OI.ZCE' 
        AND datetime>='2025-01-01' 
        AND datetime<='2025-06-30'
    """)
    oi_count = cursor.fetchone()[0]
    
    conn.close()
    
    # 写入结果文件
    with open('test_result.txt', 'w', encoding='utf-8') as f:
        f.write(f"数据库检查结果:\n")
        f.write(f"RB.SHF 数据行数: {rb_count}\n")
        f.write(f"OI.ZCE 数据行数: {oi_count}\n")
        f.write(f"\n测试成功！\n")
    
    # 也尝试打印
    print(f"数据库检查结果:")
    print(f"RB.SHF 数据行数: {rb_count}")
    print(f"OI.ZCE 数据行数: {oi_count}")
    
except Exception as e:
    with open('test_error.txt', 'w', encoding='utf-8') as f:
        f.write(f"错误: {str(e)}\n")
    print(f"错误: {str(e)}")

