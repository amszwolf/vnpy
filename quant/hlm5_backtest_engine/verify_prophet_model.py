# -*- coding: utf-8 -*-
"""验证Prophet模型是否正确保存"""

import sqlite3
import json

db_path = 'trading_signals.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    SELECT strategy_id, prophet_params, LENGTH(prophet_model) as model_size
    FROM backtest_summary
''')

result = cursor.fetchone()

if result:
    strategy_id, prophet_params_json, model_size = result
    prophet_params = json.loads(prophet_params_json)
    
    print(f"策略ID: {strategy_id}")
    print(f"\nProphet参数:")
    for key, value in prophet_params.items():
        print(f"  - {key}: {value}")
    
    print(f"\nProphet模型:")
    print(f"  - 模型大小: {model_size/1024:.2f} KB")
    print(f"  - 已保存: {'✅ 是' if model_size > 0 else '❌ 否'}")
    
    if model_size > 0:
        print(f"\n✅ Prophet模型成功保存！")
    else:
        print(f"\n❌ Prophet模型未保存！")
else:
    print("❌ 未找到记录")

conn.close()

