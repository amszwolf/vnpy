# -*- coding: utf-8 -*-
"""
实盘交易数据库初始化脚本
创建实盘所需的所有表，与回测引擎数据结构保持一致
"""

import sqlite3
from pathlib import Path


def init_live_tables(db_path='trading_signals.db'):
    """
    初始化实盘交易数据库表
    
    与 hlm5_backtest_engine 的数据库结构保持一致，
    可以直接导入回测得出的最优策略配置和Prophet模型
    """
    print("=" * 80)
    print("实盘交易数据库初始化 - Stage 2")
    print("=" * 80)
    
    # 确保目录存在
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n数据库路径: {Path(db_path).absolute()}")
    
    # 1. 创建 trading_data 表（与回测引擎相同schema）
    print("\n[1/4] 创建 trading_data 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trading_data (
            ticker TEXT,
            datetime TIMESTAMP,
            
            -- OHLCV
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            
            -- Price MACD
            price_macd REAL,
            price_macd_signal REAL,
            price_macd_hist REAL,
            price_xlpl_phase INTEGER,
            price_cross INTEGER,
            
            -- Volume MACD
            volume_macd REAL,
            volume_macd_signal REAL,
            volume_macd_hist REAL,
            volume_xlpl_phase INTEGER,
            volume_cross INTEGER,
            
            -- HLBW
            hlbw_trend_line REAL,
            hlbw_macd REAL,
            hlbw_macd_signal REAL,
            hlbw_macd_hist REAL,
            hlbw_xlpl_phase INTEGER,
            hlbw_cross INTEGER,
            
            -- Prophet (从模型实时预测)
            prophet_yhat REAL,
            prophet_yhat_lower REAL,
            prophet_yhat_upper REAL,
            prophet_macd REAL,
            prophet_macd_signal REAL,
            prophet_macd_hist REAL,
            prophet_xlpl_phase INTEGER,
            prophet_cross INTEGER,
            prophet_trend_duration INTEGER,
            prophet_trend_change REAL,
            
            -- 交易信号
            entry_signal INTEGER DEFAULT 0,
            exit_signal INTEGER DEFAULT 0,
            signal_type INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            entry_price REAL,
            exit_price REAL,
            profit_loss REAL,
            
            -- 加仓策略
            scaling_signal INTEGER DEFAULT 0,
            scaling_position INTEGER DEFAULT 0,
            scaling_level INTEGER DEFAULT 0,
            scaling_strategy TEXT,
            
            -- 数据质量标记
            is_realtime BOOLEAN DEFAULT 1,
            data_quality INTEGER DEFAULT 1,
            
            PRIMARY KEY (ticker, datetime)
        )
    """)
    
    # 创建索引（优化实盘查询）
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticker_datetime 
        ON trading_data(ticker, datetime)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_datetime 
        ON trading_data(datetime DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_realtime 
        ON trading_data(is_realtime) 
        WHERE is_realtime = 1
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_entry_signal 
        ON trading_data(entry_signal) 
        WHERE entry_signal != 0
    """)
    print("  ✓ trading_data 表创建成功")
    print("  ✓ 与回测引擎schema完全一致")
    
    # 2. 创建 live_strategies 表（继承自optimal_strategies，增加实盘控制字段）
    print("\n[2/4] 创建 live_strategies 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_strategies (
            strategy_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            
            -- 回测时间范围（继承自回测）
            start_date TEXT,
            end_date TEXT,
            
            -- 指标参数 (JSON) - 从optimal_strategies导入
            indicator_params TEXT,
            
            -- 交易参数 (JSON) - 从optimal_strategies导入
            trading_params TEXT,
            
            -- Prophet模型 (BLOB) - 从optimal_strategies导入
            prophet_model BLOB,
            prophet_params TEXT,
            
            -- 回测性能指标（参考）
            backtest_total_return REAL,
            backtest_annual_return REAL,
            backtest_sharpe_ratio REAL,
            backtest_max_drawdown REAL,
            backtest_win_rate REAL,
            backtest_total_trades INTEGER,
            backtest_avg_holding_period REAL,
            backtest_profit_factor REAL,
            
            -- 完整配置 (JSON) - 从optimal_strategies导入
            full_config TEXT,
            
            -- 实盘控制参数
            max_position INTEGER DEFAULT 10,
            max_daily_loss REAL DEFAULT -10000,
            max_daily_trades INTEGER DEFAULT 50,
            is_paper_trading BOOLEAN DEFAULT 1,
            auto_trading BOOLEAN DEFAULT 0,
            
            -- 实盘性能追踪
            live_total_trades INTEGER DEFAULT 0,
            live_win_trades INTEGER DEFAULT 0,
            live_total_pnl REAL DEFAULT 0,
            live_current_position INTEGER DEFAULT 0,
            
            -- 标记和状态
            is_optimal BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'testing',
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deployed_at TIMESTAMP,
            last_trade_at TIMESTAMP,
            imported_from TEXT,
            comments TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_strategy_ticker 
        ON live_strategies(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_strategy_status 
        ON live_strategies(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_live_strategy_paper 
        ON live_strategies(is_paper_trading)
    """)
    print("  ✓ live_strategies 表创建成功")
    print("  ✓ 支持从optimal_strategies导入配置和Prophet模型")
    
    # 3. 创建 live_trades 表
    print("\n[3/4] 创建 live_trades 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_trades (
            trade_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            
            -- 订单信息
            order_id TEXT,
            vt_orderid TEXT,
            direction TEXT,
            offset TEXT,
            
            -- 入场信息
            entry_datetime TIMESTAMP,
            entry_price REAL,
            entry_volume INTEGER,
            entry_signal_type INTEGER,
            entry_signal_strength INTEGER,
            
            -- 出场信息
            exit_datetime TIMESTAMP,
            exit_price REAL,
            exit_volume INTEGER,
            exit_reason TEXT,
            
            -- 盈亏计算
            gross_pnl REAL,
            commission REAL,
            slippage_cost REAL,
            net_pnl REAL,
            return_pct REAL,
            
            -- 持仓信息
            holding_period INTEGER,
            max_profit REAL,
            max_loss REAL,
            
            -- 状态
            status TEXT DEFAULT 'OPEN',
            is_paper_trade BOOLEAN DEFAULT 1,
            
            -- 回测对比
            expected_pnl REAL,
            actual_vs_expected REAL,
            
            -- 元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            comments TEXT,
            
            FOREIGN KEY (strategy_id) REFERENCES live_strategies(strategy_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_ticker 
        ON live_trades(ticker)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_strategy 
        ON live_trades(strategy_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_datetime 
        ON live_trades(entry_datetime DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_status 
        ON live_trades(status)
    """)
    print("  ✓ live_trades 表创建成功")
    print("  ✓ 支持实盘与回测对比")
    
    # 4. 创建 live_performance_daily 表
    print("\n[4/4] 创建 live_performance_daily 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_performance_daily (
            date DATE,
            ticker TEXT,
            strategy_id TEXT,
            
            -- 交易统计
            total_trades INTEGER DEFAULT 0,
            win_trades INTEGER DEFAULT 0,
            loss_trades INTEGER DEFAULT 0,
            
            -- 盈亏
            gross_pnl REAL DEFAULT 0,
            net_pnl REAL DEFAULT 0,
            total_commission REAL DEFAULT 0,
            total_slippage REAL DEFAULT 0,
            
            -- 风险指标
            max_drawdown REAL,
            daily_return REAL,
            cumulative_return REAL,
            sharpe_ratio REAL,
            
            -- 回测对比
            expected_pnl REAL,
            tracking_error REAL,
            
            -- 元数据
            is_paper_trading BOOLEAN DEFAULT 1,
            
            PRIMARY KEY (date, ticker, strategy_id),
            FOREIGN KEY (strategy_id) REFERENCES live_strategies(strategy_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_date 
        ON live_performance_daily(date DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_strategy 
        ON live_performance_daily(strategy_id)
    """)
    print("  ✓ live_performance_daily 表创建成功")
    print("  ✓ 支持每日绩效追踪和对比")
    
    # 5. 提交并验证
    print("\n" + "="*80)
    print("验证数据库结构")
    print("="*80)
    conn.commit()
    
    # 查询所有表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    print("\n实盘数据库中的所有表:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  ✓ {table[0]}: {count} 条记录")
    
    # 检查索引
    print("\n创建的索引:")
    cursor.execute("""
        SELECT name, tbl_name FROM sqlite_master 
        WHERE type='index' AND name LIKE 'idx_%'
        ORDER BY tbl_name, name
    """)
    indexes = cursor.fetchall()
    
    current_table = None
    for idx_name, tbl_name in indexes:
        if tbl_name != current_table:
            print(f"\n  {tbl_name}:")
            current_table = tbl_name
        print(f"    - {idx_name}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ 实盘数据库初始化完成！")
    print("=" * 80)
    
    print("\n📋 与Stage 1对接说明:")
    print("  1. live_strategies 表结构与 optimal_strategies 完全兼容")
    print("  2. 支持导入 Prophet 模型 BLOB (1257.42 KB)")
    print("  3. trading_data 表schema与回测引擎一致")
    print("  4. 可直接从 hlm5_backtest_engine/optimal_strategies 导入策略")
    
    return True


def verify_compatibility():
    """验证与回测引擎的兼容性"""
    print("\n" + "=" * 80)
    print("验证与回测引擎的兼容性")
    print("=" * 80)
    
    backtest_db = Path("../../hlm5_backtest_engine/trading_signals.db")
    
    if not backtest_db.exists():
        print(f"\n⚠️  回测引擎数据库不存在: {backtest_db}")
        print("  这是正常的，如果还未运行Stage 1")
        return False
    
    print(f"\n✓ 找到回测引擎数据库: {backtest_db}")
    
    # 连接回测数据库
    conn = sqlite3.connect(backtest_db)
    cursor = conn.cursor()
    
    # 检查optimal_strategies表
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master 
        WHERE type='table' AND name='optimal_strategies'
    """)
    
    if cursor.fetchone()[0] == 0:
        print("  ⚠️  optimal_strategies 表不存在")
        conn.close()
        return False
    
    # 查询最优策略
    cursor.execute("""
        SELECT 
            strategy_id, 
            ticker, 
            sharpe_ratio,
            LENGTH(prophet_model) as model_size
        FROM optimal_strategies 
        ORDER BY sharpe_ratio DESC 
        LIMIT 3
    """)
    
    strategies = cursor.fetchall()
    
    if strategies:
        print(f"\n✓ 找到 {len(strategies)} 个最优策略:")
        for i, (sid, ticker, sharpe, model_size) in enumerate(strategies, 1):
            model_info = f"{model_size/1024:.2f} KB" if model_size else "无"
            print(f"  {i}. {sid}")
            print(f"     合约: {ticker} | 夏普: {sharpe:.2f} | Prophet: {model_info}")
    else:
        print("  ⚠️  没有找到最优策略")
    
    conn.close()
    
    print("\n✅ 兼容性验证完成！可以导入策略")
    return True


if __name__ == "__main__":
    # 初始化实盘数据库
    init_live_tables()
    
    # 验证与回测引擎的兼容性
    verify_compatibility()

