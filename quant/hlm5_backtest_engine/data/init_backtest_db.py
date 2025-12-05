# -*- coding: utf-8 -*-
"""
回测引擎数据库初始化脚本
在现有 trading_signals.db 基础上添加新表
"""

import sqlite3
from pathlib import Path
import sys

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def init_backtest_tables(db_path='../trading_signals.db'):
    """
    初始化回测引擎的数据库表
    
    只添加新表，不修改现有的 trading_data 表
    """
    print("=" * 60)
    print("回测引擎数据库初始化")
    print("=" * 60)
    
    # 解析数据库路径
    db_file = Path(__file__).parent / db_path
    db_file = db_file.resolve()
    
    print(f"\n数据库路径: {db_file}")
    
    # 检查数据库文件是否存在
    if not db_file.exists():
        print(f"  ⚠ 数据库文件不存在，将创建新文件")
        db_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        print(f"  ✓ 数据库文件已存在")
    
    # 连接数据库
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    
    # 1. 创建 backtest_summary 表
    print("\n[1/3] 创建 backtest_summary 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backtest_summary (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON)
            indicator_params TEXT,
            
            -- 交易参数 (JSON)
            trading_params TEXT,
            
            -- Prophet模型 (序列化)
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标
            total_return REAL,
            annual_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            avg_holding_period REAL,
            profit_factor REAL,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'completed',
            
            -- 完整策略配置 (JSON)
            full_config TEXT,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_ticker 
        ON backtest_summary(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_optimal 
        ON backtest_summary(is_optimal) 
        WHERE is_optimal = 1
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_backtest_sharpe 
        ON backtest_summary(sharpe_ratio DESC)
    """)
    print("  ✓ backtest_summary 表创建成功")
    
    # 2. 创建 optimal_strategies 表
    print("\n[2/3] 创建 optimal_strategies 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS optimal_strategies (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON)
            indicator_params TEXT,
            
            -- 交易参数 (JSON)
            trading_params TEXT,
            
            -- Prophet模型 (序列化)
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标
            total_return REAL,
            annual_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            total_trades INTEGER,
            avg_holding_period REAL,
            profit_factor REAL,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'active',
            
            -- 完整策略配置 (JSON)
            full_config TEXT,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimal_ticker 
        ON optimal_strategies(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_optimal_status 
        ON optimal_strategies(status)
    """)
    print("  ✓ optimal_strategies 表创建成功")
    
    # 3. 提交并验证
    print("\n[3/3] 提交更改并验证...")
    conn.commit()
    
    # 查询所有表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    print("\n数据库中的所有表:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table[0]}: {count} 条记录")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("数据库初始化完成！")
    print("=" * 60)
    print("\n验证结果:")
    print("  ✅ backtest_summary 表已创建")
    print("  ✅ optimal_strategies 表已创建")
    print("  ✅ 所有索引已创建")
    print("  ✅ 现有表未受影响")
    
    return True


if __name__ == "__main__":
    # 默认数据库路径（相对于data目录）
    db_path = "../trading_signals.db"
    
    # 初始化表
    success = init_backtest_tables(db_path)
    
    if success:
        print("\n✅ 步骤1.1完成！可以继续步骤1.2")
    else:
        print("\n❌ 步骤1.1失败，请检查错误信息")

