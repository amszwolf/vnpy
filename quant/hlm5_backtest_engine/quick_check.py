"""快速检查数据"""
import pandas as pd
import sqlite3

output = []

try:
    conn = sqlite3.connect('trading_signals.db')
    
    # 检查RB.SHF
    query = """
    SELECT COUNT(*) as total, 
           SUM(CASE WHEN Entry_Signal != 0 THEN 1 ELSE 0 END) as entries,
           SUM(CASE WHEN Exit_Signal = 1 THEN 1 ELSE 0 END) as exits,
           MIN(datetime) as min_date,
           MAX(datetime) as max_date
    FROM trading_data 
    WHERE ticker = 'RB.SHF'
      AND datetime >= '2025-01-01'
      AND datetime <= '2025-06-30'
    """
    
    df = pd.read_sql(query, conn)
    output.append(f"RB.SHF数据检查:")
    output.append(f"  总行数: {df['total'].iloc[0]}")
    output.append(f"  入场信号: {df['entries'].iloc[0]}")
    output.append(f"  出场信号: {df['exits'].iloc[0]}")
    output.append(f"  日期范围: {df['min_date'].iloc[0]} 至 {df['max_date'].iloc[0]}")
    
    # 检查OI.ZCE
    query = query.replace('RB.SHF', 'OI.ZCE')
    df = pd.read_sql(query, conn)
    output.append(f"\nOI.ZCE数据检查:")
    output.append(f"  总行数: {df['total'].iloc[0]}")
    output.append(f"  入场信号: {df['entries'].iloc[0]}")
    output.append(f"  出场信号: {df['exits'].iloc[0]}")
    output.append(f"  日期范围: {df['min_date'].iloc[0]} 至 {df['max_date'].iloc[0]}")
    
    conn.close()
    
except Exception as e:
    output.append(f"错误: {str(e)}")

# 写入文件
with open('data_check_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("检查完成，结果已写入 data_check_result.txt")

