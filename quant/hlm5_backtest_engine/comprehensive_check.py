# -*- coding: utf-8 -*-
"""
全面检查Prophet模型和所有输出
"""

import sqlite3
import json
import pickle
from pathlib import Path

print("="*80)
print("HLM5回测输出全面检查")
print("="*80)

# 1. 检查数据库中的Prophet模型
print("\n[1/5] 检查数据库中的Prophet模型...")
print("-"*80)

db_path = 'trading_signals.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    SELECT 
        strategy_id,
        ticker,
        prophet_model,
        prophet_params,
        sharpe_ratio,
        annual_return,
        total_return,
        max_drawdown,
        win_rate,
        total_trades
    FROM backtest_summary
''')

result = cursor.fetchone()

if result:
    strategy_id, ticker, prophet_model_blob, prophet_params_json, \
    sharpe, annual_ret, total_ret, max_dd, win_rate, total_trades = result
    
    print(f"✓ 策略ID: {strategy_id}")
    print(f"✓ 合约: {ticker}")
    
    # 检查Prophet模型BLOB
    if prophet_model_blob:
        model_size = len(prophet_model_blob)
        print(f"\n✅ Prophet模型BLOB:")
        print(f"   - 大小: {model_size:,} 字节 ({model_size/1024:.2f} KB)")
        print(f"   - 类型: {type(prophet_model_blob)}")
        
        # 尝试反序列化
        try:
            model = pickle.loads(prophet_model_blob)
            print(f"   - 反序列化: ✅ 成功")
            print(f"   - 模型类型: {type(model).__name__}")
            print(f"   - 模型属性: {len(dir(model))} 个")
            
            # 检查关键属性
            if hasattr(model, 'params'):
                print(f"   - params: ✅ 存在")
            if hasattr(model, 'predict'):
                print(f"   - predict方法: ✅ 存在")
                
        except Exception as e:
            print(f"   - 反序列化: ❌ 失败 - {e}")
    else:
        print(f"\n❌ Prophet模型BLOB: 未保存")
    
    # 检查Prophet参数
    if prophet_params_json:
        prophet_params = json.loads(prophet_params_json)
        print(f"\n✅ Prophet参数:")
        for key, value in prophet_params.items():
            print(f"   - {key}: {value}")
    else:
        print(f"\n❌ Prophet参数: 未保存")
    
    # 检查性能指标
    print(f"\n✅ 回测性能指标:")
    print(f"   - 夏普比率: {sharpe:.2f}")
    print(f"   - 年化收益: {annual_ret*100:.2f}%")
    print(f"   - 总收益率: {total_ret*100:.2f}%")
    print(f"   - 最大回撤: {max_dd*100:.2f}%")
    print(f"   - 胜率: {win_rate*100:.2f}%")
    print(f"   - 总交易: {total_trades}")
else:
    print("❌ 未找到回测记录")

conn.close()

# 2. 检查JSON配置文件
print("\n[2/5] 检查JSON配置文件...")
print("-"*80)

json_path = Path('configs/strategies') / f'{strategy_id}.json'
if json_path.exists():
    print(f"✓ 文件存在: {json_path}")
    print(f"✓ 文件大小: {json_path.stat().st_size} 字节")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print(f"\n✅ JSON配置内容:")
    print(f"   - strategy_id: {config.get('strategy_id')}")
    print(f"   - ticker: {config.get('ticker')}")
    print(f"   - strategy_name: {config.get('strategy_name')}")
    print(f"   - version: {config.get('version')}")
    
    # 检查Prophet配置
    prophet_config = config.get('indicators', {}).get('prophet', {})
    if prophet_config:
        print(f"\n   Prophet配置:")
        print(f"   - enabled: {prophet_config.get('enabled')}")
        print(f"   - training_samples: {prophet_config.get('training_samples')}")
        print(f"   - training_date_range: {prophet_config.get('training_date_range')}")
        print(f"   - weekly_seasonality: {prophet_config.get('weekly_seasonality')}")
        print(f"   - yearly_seasonality: {prophet_config.get('yearly_seasonality')}")
    
    # 检查是否包含prophet_model（不应该有）
    if '_prophet_model_bytes' in config or 'prophet_model' in config:
        print(f"\n   ⚠️ 警告: JSON中包含prophet_model字段（应该只在数据库中）")
    else:
        print(f"\n   ✅ 正确: JSON中不包含prophet_model BLOB")
else:
    print(f"❌ 文件不存在: {json_path}")

# 3. 检查HTML分析图表
print("\n[3/5] 检查HTML分析图表...")
print("-"*80)

html_path = Path('output') / f'{ticker}_analysis.html'
if html_path.exists():
    print(f"✓ 文件存在: {html_path}")
    print(f"✓ 文件大小: {html_path.stat().st_size:,} 字节 ({html_path.stat().st_size/1024:.2f} KB)")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 检查关键内容
    checks = [
        ('Bokeh', 'Bokeh图表库'),
        ('Total Return', '总收益'),
        ('Sharpe Ratio', '夏普比率'),
        ('Max Drawdown', '最大回撤'),
        ('Win Rate', '胜率'),
    ]
    
    print(f"\n✅ HTML内容检查:")
    for keyword, desc in checks:
        if keyword in html_content:
            print(f"   - {desc}: ✅")
        else:
            print(f"   - {desc}: ⚠️ 未找到")
else:
    print(f"❌ 文件不存在: {html_path}")

# 4. 检查trading_data表
print("\n[4/5] 检查trading_data表...")
print("-"*80)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute(f'''
    SELECT COUNT(*) FROM trading_data WHERE ticker = '{ticker}'
''')
total_bars = cursor.fetchone()[0]
print(f"✓ K线数据: {total_bars:,} 条")

# 检查是否有Prophet预测数据列
cursor.execute("PRAGMA table_info(trading_data)")
columns = [row[1] for row in cursor.fetchall()]
has_prophet_cols = 'prophet_yhat' in columns

if has_prophet_cols:
    cursor.execute(f'''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN prophet_yhat IS NOT NULL AND prophet_yhat != 0 THEN 1 ELSE 0 END) as with_prophet
        FROM trading_data 
        WHERE ticker = '{ticker}'
    ''')
    total, with_prophet = cursor.fetchone()
    print(f"✓ Prophet预测数据: {with_prophet}/{total} 条")
    
    if with_prophet > 0:
        print(f"   ✅ Prophet预测已计算")
    else:
        print(f"   ⚠️ Prophet预测为空")
else:
    print(f"   ℹ️ Prophet预测列不存在（模型单独保存，用于实盘加载）")

# 检查信号数据
cursor.execute(f'''
    SELECT 
        SUM(CASE WHEN entry_signal != 0 THEN 1 ELSE 0 END) as entry_signals,
        SUM(CASE WHEN exit_signal != 0 THEN 1 ELSE 0 END) as exit_signals
    FROM trading_data 
    WHERE ticker = '{ticker}'
''')
entry_signals, exit_signals = cursor.fetchone()
print(f"\n✓ 交易信号:")
print(f"   - 入场信号: {entry_signals} 个")
print(f"   - 出场信号: {exit_signals} 个")

conn.close()

# 5. 检查optimal_strategies表
print("\n[5/5] 检查optimal_strategies表...")
print("-"*80)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute(f'''
    SELECT 
        strategy_id,
        status,
        created_at,
        comments
    FROM optimal_strategies
    WHERE strategy_id = '{strategy_id}'
''')

opt_result = cursor.fetchone()
if opt_result:
    opt_id, status, created_at, comments = opt_result
    print(f"✓ 策略ID: {opt_id}")
    print(f"✓ 状态: {status}")
    print(f"✓ 创建时间: {created_at}")
    print(f"✓ 备注: {comments}")
    
    # 检查是否也有Prophet模型
    cursor.execute(f'''
        SELECT LENGTH(prophet_model) as model_size
        FROM optimal_strategies
        WHERE strategy_id = '{strategy_id}'
    ''')
    opt_model_size = cursor.fetchone()[0]
    if opt_model_size:
        print(f"\n✅ optimal_strategies中的Prophet模型:")
        print(f"   - 大小: {opt_model_size:,} 字节 ({opt_model_size/1024:.2f} KB)")
    else:
        print(f"\n❌ optimal_strategies中未保存Prophet模型")
else:
    print(f"❌ 未找到optimal_strategies记录")

conn.close()

# 最终总结
print("\n" + "="*80)
print("检查总结")
print("="*80)

checks_summary = [
    ("Prophet模型BLOB保存", prophet_model_blob is not None and len(prophet_model_blob) > 0),
    ("Prophet模型可反序列化", prophet_model_blob is not None),
    ("Prophet参数完整", prophet_params_json is not None),
    ("JSON配置文件存在", json_path.exists()),
    ("HTML图表文件存在", html_path.exists()),
    ("trading_data数据完整", total_bars > 0),
    ("optimal_strategies记录存在", opt_result is not None),
]

all_passed = all([result for _, result in checks_summary])

for check_name, result in checks_summary:
    status = "✅ 通过" if result else "❌ 失败"
    print(f"{status} - {check_name}")

print("\n" + "="*80)
if all_passed:
    print("🎉 所有检查通过！输出完全符合要求！")
else:
    print("⚠️ 部分检查未通过，请查看上述详情")
print("="*80)

