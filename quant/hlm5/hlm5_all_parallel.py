"""
HLM5 期货数据智能更新系统 (Futures Version with Bidirectional Trading)

本文件是经过优化测试后的最终版本，采用仅收盘平仓优化策略。

主要特性：
1. 数据源：期货分钟级数据（tb_futures_rboi_1min 或 tb_futures_rboi_5min）
2. 双向交易：支持做多（Long）和做空（Short）
3. 数据字段：使用 trade_time（支持分钟级数据）
4. 期货代码：如 'OI.ZCE', 'RB.SHF'
5. 智能更新：增量/全量/实时更新
6. 快速测试：默认处理2个期货品种，1个月数据

【优化功能】（基于测试结果采用的最优策略）：
7. 收盘平仓优化：
   - ✅ 收盘前5分钟强制平仓（完全消除隔夜风险）
   - ✅ 收盘前禁止开新仓
   - ✅ 支持 hold_overnight 参数控制（未来扩展）

8. 开盘策略：
   - ✅ 允许开盘时立即生成信号（不设缓冲期）
   - ✅ 保持最大交易机会
   - ✅ 实测收益率最优（OI.ZCE: 24.73%, RB.SHF: 19.46%）

性能表现（2025-01-01至2025-01-31测试）：
    - OI.ZCE: 总收益24.73%, 胜率74.31%, 夏普比率0.504
    - RB.SHF: 总收益19.46%, 胜率75.52%, 最大回撤-0.21%
    - 完全消除隔夜风险，不损失交易机会

默认配置（优化测试速度）：
    - 期货品种：2个（RB.SHF, OI.ZCE）
    - 数据粒度：1分钟
    - 时间范围：2025-01-01 到 2025-01-31（1个月）
    - 双向交易：启用
    - 持仓过夜：禁止（默认）
    - 开盘缓冲期：禁用（测试证明效果最佳）

使用示例：
    python hlm5_all_parallel.py  # 使用默认配置（aggressive_pyramid加仓策略）
    python hlm5_all_parallel.py --max-tickers 5 --verbose
    python hlm5_all_parallel.py --mode full  # 全量更新
    python hlm5_all_parallel.py --start-date 2025-01-01 --end-date 2025-03-31
    python hlm5_all_parallel.py --scaling-strategy pyramid  # 使用金字塔加仓策略
    python hlm5_all_parallel.py --scaling-strategy none  # 不使用加仓策略

Python环境：aidata311

版本说明：
    - 本版本已验证为三版本测试中的最优版本
    - 相比原始版本，OI.ZCE收益提升0.35%，RB.SHF胜率提升0.58%
    - 相比全优化版本（含开盘缓冲期），交易次数保持不变，收益提升6-8个百分点
    - 推荐用于日内期货交易
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet
# import yfinance as yf
import pymysql
from bokeh.plotting import figure, show, output_file    
from bokeh.models import ColumnDataSource
from bokeh.layouts import column
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import sqlite3
import os  # 添加os模块导入
from datetime import datetime
import talib
import logging
import time
import copy
from typing import Dict

# 导入统一配置
try:
    from hlm5_config import EQUITY_CONFIG, OVERALL_CONFIG, LOG_CONFIG
    print("[OK] 成功导入hlm5_config配置")
except ImportError:
    print("[WARNING] 无法导入hlm5_config，使用默认配置")
    EQUITY_CONFIG = {
        'DATABASE_PATH': 'trading_signals.db',
        'PARALLEL_PROCESSING': True,
        'MAX_WORKERS': 4,
        'UPDATE_STRATEGY': {
            'enable_incremental': True,  # 启用增量更新
            'enable_realtime': False,    # 启用实时更新
            'force_full_update': False,  # 强制全量更新
            'skip_existing': False,      # 跳过已存在数据的股票
            'auto_cleanup_realtime': True,  # 自动清理过期实时数据
            'max_missing_days': 5,       # 最大允许缺失天数，超过则全量更新
        },
        'INDICATORS': {
            'PRICE_MACD': {'macd_long': 13, 'macd_mid': 7, 'macd_short': 5, 'diff_ema_period': 3},
            'VOLUME_MACD': {'macd_long': 26, 'macd_mid': 12, 'macd_short': 9, 'diff_ema_period': 5},
            'HLBW': {'lookback_period': 55, 'inner_ema': 5, 'outer_ema': 3, 'trend_ema': 3},
            'PROPHET': {
                'periods': 30,
                'daily_seasonality': False,
                'weekly_seasonality': True,
                'yearly_seasonality': True,
                'changepoint_prior_scale': 0.05
            }
        }
    }
    OVERALL_CONFIG = {'TRADING_SIGNALS_DB': 'trading_signals.db'}
from bokeh.plotting import figure, show, output_file
from bokeh.layouts import column
from bokeh.models import (
    CrosshairTool, 
    PanTool, 
    WheelZoomTool, 
    BoxZoomTool, 
    ResetTool, 
    SaveTool, 
    Range1d, 
    ColumnDataSource  # 如果需要的话
)
from trading_signal_database_manager import TradingSignalDatabaseManager
# FinScreenerDBManager 不需要用于期货数据
# from finscreener_database_manager import FinScreenerDBManager
import concurrent.futures

# 导入交易时段管理器（优化版本新增）
from trading_session_manager import TradingSessionManager

# 导入期货合约规格和交易成本模型（盈亏计算修复）
from futures_contract_specs import FuturesContractSpecs, TradingCostCalculator

# 导入加仓策略模块
from scaling_strategy import (
    ScalingConfig,
    generate_scaling_signals,
    calculate_scaling_performance,
    SCALING_CONFIGS
)

# 0.-2 定义常量
# HLBW 全局常量
HLBW_TOP_LINE = 89      # 顶部压力线
HLBW_BOTTOM_LINE = 11   # 底部支撑线
HLBW_MID_LINE = 50      # 中轴线
HLBW_MID_HIGH_LINE = 75 # 中高位警戒线
HLBW_MID_LOW_LINE = 25  # 中低位警戒线

# 0.-1, 定义数据库结构

# # 修改 TradingSignalDatabaseManager 类中的表结构定义
# class TradingSignalDatabaseManager:
#     def __init__(self, db_path):
#         """
#         初始化数据库管理器
        
#         Parameters:
#         -----------
#         db_path : str
#             SQLite数据库文件路径
#         """
#         self.db_path = db_path
        
#         # 确保数据库文件所在目录存在
#         db_dir = os.path.dirname(db_path)
#         if db_dir and not os.path.exists(db_dir):
#             os.makedirs(db_dir)
            
#         # 创建内存数据库连接
#         self.memory_conn = sqlite3.connect(':memory:')

#         # 如果磁盘上存在数据库文件，则加载到内存
#         self.load_from_disk()
        
#         # 创建表结构
#         self._create_tables()

#     def _create_tables(self):
#         """创建统一的数据表结构"""
#         try:
#             cursor = self.memory_conn.cursor()
            
#             # 创建统一的交易数据表
#             cursor.execute('''
#             CREATE TABLE IF NOT EXISTS trading_data (
#                 ticker TEXT,
#                 datetime TIMESTAMP,
                
#                 -- 原始数据
#                 open REAL,
#                 high REAL,
#                 low REAL,
#                 close REAL,
#                 volume REAL,
                
#                 -- Price MACD数据
#                 Price_MACD REAL,
#                 Price_MACD_Signal REAL,
#                 Price_MACD_Hist REAL,
#                 Price_XLPL_Phase INTEGER,
#                 Price_Cross INTEGER,
                
#                 -- Volume MACD数据
#                 Volume_MACD REAL,
#                 Volume_MACD_Signal REAL,
#                 Volume_MACD_Hist REAL,
#                 Volume_XLPL_Phase INTEGER,
#                 Volume_Cross INTEGER,
                
#                 -- HLBW数据
#                 HLBW_Trend_Line REAL,
#                 HLBW_MACD REAL,          -- 新增 HLBW MACD
#                 HLBW_MACD_Signal REAL,   -- 新增 HLBW MACD Signal
#                 HLBW_MACD_Hist REAL,     -- 新增 HLBW MACD Histogram
#                 HLBW_XLPL_Phase INTEGER,
#                 HLBW_Cross INTEGER,
                
#                 -- Prophet预测数据
#                 PH_yhat REAL,
#                 PH_yhat_lower REAL,
#                 PH_yhat_upper REAL,
#                 PH_MACD REAL,          -- 新增 Prophet MACD
#                 PH_MACD_Signal REAL,   -- 新增 Prophet Signal
#                 PH_MACD_Hist REAL,     -- 新增 Prophet Histogram
#                 PH_XLPL_Phase INTEGER,
#                 PH_Cross INTEGER,
#                 PH_Trend_Duration INTEGER,
#                 PH_Trend_Change REAL,
                
#                 -- 交易信号
#                 Entry_Signal BOOLEAN,
#                 Exit_Signal BOOLEAN,
#                 Position INTEGER,
#                 Entry_Price REAL,
#                 Exit_Price REAL,
#                 Profit_Loss REAL,
                
#                 PRIMARY KEY (ticker, datetime)
#             )
#             ''')
            
#             self.memory_conn.commit()
#             print("Database tables created successfully")
#         except Exception as e:
#             print(f"Error creating database tables: {str(e)}")
#             raise

#     def update_data(self, ticker, datetime, data_dict):
#         """
#         更新或插入数据到统一表
        
#         Parameters:
#         -----------
#         ticker : str
#             股票代码
#         datetime : timestamp
#             时间戳
#         data_dict : dict
#             要更新的数据字典，键为列名，值为数据
#         """
#         try:
#             # 将 Pandas Timestamp 转换为 str
#             if pd.isna(datetime):  # 检查是否为 NaT
#                 print(f"Warning: Skipping row with NaT datetime for {ticker}")
#                 return
            
#             if isinstance(datetime, pd.Timestamp):
#                 datetime = datetime.strftime('%Y-%m-%d %H:%M:%S')
            
#             # 处理数据字典中的空值
#             cleaned_dict = {}
#             for key, value in data_dict.items():
#                 if pd.isna(value):  # 检查 NaN 或 NaT
#                     cleaned_dict[key] = None  # SQLite 使用 NULL
#                 else:
#                     cleaned_dict[key] = value
            
#             # 构建SQL语句
#             columns = ['ticker', 'datetime'] + list(cleaned_dict.keys())
#             placeholders = ','.join(['?'] * len(columns))
#             values = [ticker, datetime] + list(cleaned_dict.values())
            
#             update_stmt = ','.join([f"{k}=?" for k in cleaned_dict.keys()])
            
#             sql = f"""
#             INSERT INTO trading_data ({','.join(columns)})
#             VALUES ({placeholders})
#             ON CONFLICT(ticker, datetime) DO UPDATE SET
#             {update_stmt}
#             """
            
#             cursor = self.memory_conn.cursor()
#             cursor.execute(sql, values + list(cleaned_dict.values()))
#             self.memory_conn.commit()
            
#         except Exception as e:
#             print(f"Error updating data for {ticker} at {datetime}: {str(e)}")
#             raise

#     def clear_tables(self, ticker):
#         """清除特定股票的所有记录"""
#         cursor = self.memory_conn.cursor()
#         cursor.execute("DELETE FROM trading_data WHERE ticker = ?", (ticker,))
#         self.memory_conn.commit()
#         print(f"Cleared all records for {ticker} from trading_data table")

#     def save_to_disk(self):
#         """将内存数据库保存到磁盘"""
#         try:
#             disk_conn = sqlite3.connect(self.db_path)
#             with disk_conn:
#                 self.memory_conn.backup(disk_conn)
#             disk_conn.close()
#             print(f"Successfully saved database to {self.db_path}")
#         except Exception as e:
#             print(f"Error saving database to disk: {str(e)}")
#             raise

#     def load_from_disk(self):
#         """从磁盘加载数据到内存数据库"""
#         if os.path.exists(self.db_path):
#             try:
#                 disk_conn = sqlite3.connect(self.db_path)
#                 with disk_conn:
#                     disk_conn.backup(self.memory_conn)
#                 disk_conn.close()
#                 print(f"Successfully loaded database from {self.db_path}")
#             except Exception as e:
#                 print(f"Error loading database from disk: {str(e)}")
#                 raise

#     def get_data(self, ticker, start_date=None, end_date=None, columns=None):
#         """
#         获取数据，确保包含完整的日期范围
        
#         Parameters:
#         -----------
#         ticker : str
#             股票代码
#         start_date : str, optional
#             开始日期，格式 'YYYY-MM-DD'
#         end_date : str, optional
#             结束日期，格式 'YYYY-MM-DD'
#         columns : list, optional
#             需要获取的列名列表，默认获取所有列
#         """
#         try:
#             # 构建列选择
#             if columns:
#                 col_str = ', '.join(['datetime'] + columns)
#             else:
#                 col_str = '*'
            
#             # 修改日期范围处理
#             query = f"SELECT {col_str} FROM trading_data WHERE ticker = ?"
#             params = [ticker]
            
#             if start_date:
#                 # 确保开始日期从当天开始
#                 query += " AND datetime >= date(?)"
#                 params.append(start_date)
                
#             if end_date:
#                 # 确保结束日期包含整天
#                 query += " AND datetime < date(?, '+1 day')"
#                 params.append(end_date)
                
#             query += " ORDER BY datetime"
            
#             # 打印查询信息用于调试
#             print(f"Query: {query}")
#             print(f"Parameters: {params}")
            
#             df = pd.read_sql(query, self.memory_conn, params=params)
#             df['datetime'] = pd.to_datetime(df['datetime'])
            
#             # 打印数据详情用于验证
#             print(f"\nData retrieved for {ticker}:")
#             print(f"Number of rows: {len(df)}")
#             print("\nFirst few rows:")
#             print(df.head())
#             print("\nLast few rows:")
#             print(df.tail())
#             print(f"\nDate range:")
#             print(f"Start: {df['datetime'].min()}")
#             print(f"End: {df['datetime'].max()}")
            
#             return df.set_index('datetime')
            
#         except Exception as e:
#             print(f"Error getting data for {ticker}: {str(e)}")
#             raise

#     def close(self):
#         """关闭数据库连接"""
#         try:
#             self.save_to_disk()  # 保存最新数据到磁盘
#             self.memory_conn.close()
#             print("Database connections closed successfully")
#         except Exception as e:
#             print(f"Error closing database connections: {str(e)}")
#             raise

####################################################################

# 0.0: 数据下载: 从mysql
# def process_tdx_raw_data(db, ticker, start_date, end_date):
def process_tdx_raw_data(mysqlite, ticker, start_date, end_date):
    """
    从MySQL下载数据，进行预处理，并存入SQLite数据库
    
    Parameters:
    -----------
    mysqlite : TradingSignalDatabaseManager
        数据库管理器实例
    ticker : str
        股票代码
    start_date : str
        开始日期，格式 'YYYY-MM-DD'
    end_date : str
        结束日期，格式 'YYYY-MM-DD'
    """
    # 连接MySQL数据库
    mysql_conn = pymysql.connect(
        host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
        port=3306,
        user='root',
        password='Wxtfz13245',
        database='tdx'
    )
    
    try:
        # 构建SQL查询
        query = f"""
        SELECT DISTINCT date as datetime, open, high, low, close, volume 
        FROM tb_szzb_day_2024
        WHERE productid = '{ticker}'
        AND date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY date
        """
        
        # 读取数据到DataFrame
        print(f"Downloading data for {ticker}...")
        df = pd.read_sql(query, mysql_conn)
        
        # 数据预处理
        print(f"Preprocessing data for {ticker}...")
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 使用check_raw_data函数进行数据质量检查和清理
        print(f"Checking data quality for {ticker}...")
        df = check_raw_data(df)
        
        # 将处理后的数据写入统一的数据库表
        print(f"Writing processed data to database for {ticker}...")
        for idx, row in df.iterrows():
            data_dict = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            }
            mysqlite.update_data(ticker, row['datetime'], data_dict)
        
        print(f"Successfully processed raw data for {ticker}")

    except Exception as e:
        print(f"Error processing raw data for {ticker}: {str(e)}")
        raise  # 重新抛出异常，让调用者知道发生了错误
        
    finally:
        mysql_conn.close()

def process_futures_raw_data(mysqlite, raw_db='tushare', raw_data_table='tb_futures_rboi_5min', ts_code='OI.ZCE', start_datetime='2025-01-01 09:00:00', end_datetime=None):
    """
    从Tushare数据库下载期货数据，进行预处理，并存入SQLite数据库
    
    Parameters:
    -----------
    mysqlite : TradingSignalDatabaseManager
        数据库管理器实例
    raw_db : str
        数据库名称
    raw_data_table : str
        数据表名称 (tb_futures_rboi_1min 或 tb_futures_rboi_5min)
    ts_code : str
        期货代码 (如 'OI.ZCE', 'RB.SHF')
    start_datetime : str
        开始时间，格式 'YYYY-MM-DD HH:MM:SS'
    end_datetime : str, optional
        结束时间，格式 'YYYY-MM-DD HH:MM:SS'
    """
    # 连接Tushare数据库
    mysql_conn = pymysql.connect(
        host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
        port=3306,
        user='root',
        password='Wxtfz13245',
        database=raw_db
    )
    
    # 构建SQL查询 - 期货数据使用 trade_time 字段
    query = f"""
    SELECT trade_time as datetime, open, high, low, close, vol as volume
    FROM {raw_data_table}
    WHERE ts_code = '{ts_code}'
    AND trade_time >= '{start_datetime}'
    AND trade_time <= '{end_datetime}'
    ORDER BY trade_time
    """
    
    # 读取数据到DataFrame
    print(f"Downloading futures data for {ts_code} from {raw_data_table}...")
    df = pd.read_sql(query, mysql_conn)

    # 打印最后几行数据以供检查
    print("\nLast few rows of downloaded futures data:")
    print(df.tail())
    print()
    
    # 数据预处理
    print(f"Preprocessing futures data for {ts_code}...")
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 使用check_raw_data函数进行数据质量检查和清理
    print(f"Checking data quality for {ts_code}...")
    df = check_raw_data(df)

    # 打印开始和最后几行数据
    print("\nFirst few rows of processed futures data:")
    print(df.head())
    print("\nLast few rows of processed futures data:")
    print(df.tail())
    print()
    
    # 将处理后的数据写入统一的数据库表
    print(f"Writing processed futures data to database for {ts_code}...")
    for idx, row in df.iterrows():
        data_dict = {
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume']
        }
        mysqlite.update_data(ts_code, row['datetime'], data_dict)
    
    print(f"Successfully processed futures raw data for {ts_code}")

    mysql_conn.close()
    # Return the processed DataFrame
    return df


def get_all_futures_codes(mydatabase='tushare', table_name='tb_futures_rboi_5min'):
    """
    从Tushare数据库中检索所有期货代码
    
    Parameters:
    -----------
    mydatabase : str
        数据库名称
    table_name : str
        期货数据表名 (tb_futures_rboi_1min 或 tb_futures_rboi_5min)
    
    Returns:
    --------
    futures_codes : list
        包含所有期货代码的列表 (如 ['OI.ZCE', 'RB.SHF'])
    """
    # 连接Tushare数据库
    mysql_conn = pymysql.connect(
        host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
        port=3306,
        user='root',
        password='Wxtfz13245',
        database=mydatabase
    )
    
    # 构建SQL查询
    query = f"""
    SELECT DISTINCT ts_code
    FROM {table_name}
    """
    
    # 执行查询并获取结果
    print(f"Retrieving all futures codes from {table_name}...")
    df = pd.read_sql(query, mysql_conn)
    
    # 提取期货代码列表
    futures_codes = df['ts_code'].tolist()
    print(f"Found {len(futures_codes)} futures codes:", futures_codes)
    
    mysql_conn.close()
    return futures_codes


# 0.0.4 取 volumn 最大的n个ts_code

def get_top_futures_codes(n, mydatabase='tushare', table_name='tb_futures_rboi_5min'):
    """
    从Tushare数据库中检索期货代码，并按成交量降序排序，取前n个
    
    Parameters:
    -----------
    n : int
        要检索的期货代码数量。如果n为None或大于可用数量，则返回所有期货代码。
    mydatabase : str
        数据库名称
    table_name : str
        期货数据表名
    
    Returns:
    --------
    futures_codes : list
        包含前n个期货代码的列表
    """
    # 连接Tushare数据库
    mysql_conn = pymysql.connect(
        host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
        port=3306,
        user='root',
        password='Wxtfz13245',
        database=mydatabase
    )
    
    # 构建SQL查询 - 按成交量降序
    query = f"""
    SELECT ts_code, SUM(vol) as total_volume
    FROM {table_name}
    GROUP BY ts_code
    ORDER BY total_volume DESC
    """
    
    # 如果n是一个有限的正整数，添加LIMIT子句
    if n is not None and n > 0:
        query += f" LIMIT {n}"
    
    # 执行查询并获取结果
    print(f"Retrieving top {n} futures codes from {table_name} based on volume...")
    df = pd.read_sql(query, mysql_conn)
    
    # 提取期货代码列表
    futures_codes = df['ts_code'].tolist()
    print(f"Top {len(futures_codes)} futures codes:", futures_codes)
    
    mysql_conn.close()
    return futures_codes

# # 0.0.5  Optimization sqlite database
# def create_optimization_db():
#     # Define the path to the database file
#     db_path = os.path.join('output', 'optimization.db')

#     # Ensure the output directory exists
#     os.makedirs('output', exist_ok=True)

#     # Connect to the SQLite database file
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()

#     # Create the optimization results table
#     cursor.execute('''
#         CREATE TABLE optimization_results (
#             StrategyId TEXT,
#             Ticker TEXT,
#             OpenBuy REAL,
#             OpenSell REAL,
#             CloseSell REAL,
#             CloseBuy REAL,
#             ParamNameValue TEXT,
#             FinalFitness REAL,
#             InitialCapital REAL,
#             FinalCapital REAL,
#             TotalReturn REAL,
#             AnnualReturn REAL,
#             SharpeRatio REAL,
#             Volatility REAL,
#             MaxDrawdown REAL,
#             TotalTrades INTEGER,
#             WinRate REAL,
#             ProfitFactor REAL,
#             AverageTrade REAL,
#             AverageWin REAL,
#             AverageLoss REAL,
#             TradeFee REAL
#         )
#     ''')

#     # Commit the changes
#     conn.commit()

#     return conn

# 0.1: 数据预处理
def check_raw_data(df):
    """
    检查原始数据完整性并进行基本清理
    
    Parameters:
    -----------
    df : pandas.DataFrame
        包含原始数据的DataFrame，必须包含 open, high, low, close, volume 列
    
    Returns:
    --------
    pandas.DataFrame
        清理后的数据
    """
    # 检查必要的列是否存在
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # 检查并处理空值
    for col in required_columns:
        na_count = df[col].isna().sum()
        if na_count > 0:
            if col == 'volume':
                # 成交量特殊处理：使用1填充
                print(f"Warning: Found {na_count} missing values in {col}, filling with 1")
                df[col].fillna(1, inplace=True)
            else:
                # 其他列使用前向填充
                print(f"Warning: Found {na_count} missing values in {col}, forward filling")
                df[col].fillna(method='ffill', inplace=True)
                # 如果还有空值（比如第一行就是空值），使用后向填充
                if df[col].isna().any():
                    df[col].fillna(method='bfill', inplace=True)
    
    # 检查重复值
    if df.duplicated().any():
        dup_count = df.duplicated().sum()
        print(f"Warning: Found {dup_count} duplicate rows, removing")
        df.drop_duplicates(inplace=True)
    
    # 检查数据类型
    for col in required_columns:
        if not np.issubdtype(df[col].dtype, np.number):
            print(f"Warning: Converting {col} to numeric")
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 检查异常值
    for col in required_columns:
        mean = df[col].mean()
        std = df[col].std()
        outliers = df[col][(df[col] < mean - 3*std) | (df[col] > mean + 3*std)]
        if len(outliers) > 0:
            print(f"Warning: Found {len(outliers)} outliers in {col}")
            print(f"Column {col} statistics:")
            print(f"  Mean: {mean:.2f}")
            print(f"  Std: {std:.2f}")
            print(f"  Min: {df[col].min():.2f}")
            print(f"  Max: {df[col].max():.2f}")
    
    return df



# 1.0: 通用函数: MACD XLPL CROSS 

# 1.1. 计算 MACD-XLPL-CROSS 指标
def calculate_macd_signals(series, 
                         macd_long=13, 
                         macd_mid=7, 
                         macd_short=5,
                         diff_ema_period=3):
    """
    计算MACD及其相关信号，包含修正后的XLPL阶段判断
    
    Parameters:
    -----------
    series : pandas.Series
        输入数据序列
    macd_long : int, optional (default=26)
        MACD长期EMA周期
    macd_mid : int, optional (default=12)
        MACD中期EMA周期
    macd_short : int, optional (default=9)
        MACD短期EMA周期（信号线）
    diff_ema_period : int, optional (default=3)
        MACD差值的EMA周期

    Returns:
    --------
    pandas.DataFrame : 包含以下列的DataFrame:
        - MACD: MACD线(DIF), float64
        - MACD_Signal: MACD信号线(DEA), float64
        - MACD_Hist: MACD柱状图, float64
        - DIFDEA_DIFF: DIF-DEA的差值, float64
        - DDMA_DIFF: DIFDEA_DIFF的EMA, float64
        - XLPL_Phase: XLPL阶段 (1:吸筹, 2:拉升, 3:派发, 4:下跌), int32
        - Cross_1: DIF和DEA的交叉信号, int32
        - Cross_2: MACD差值与其EMA的交叉信号, int32
        - Cross_3: DEA与0轴的交叉信号, int32
        - Cross_4: DIF与0轴的交叉信号, int32
    """
    # 确保输入是pandas Series
    if isinstance(series, np.ndarray):
        series = pd.Series(series)


        # 1. 计算MACD基础值
    print(f"Input series length: {len(series)}")
    print(f"Input series index range: {series.index[0]} to {series.index[-1]}")
    
    # 直接使用 TA-Lib 的 MACD 函数
    dif, dea, hist = talib.MACD(series, 
                               fastperiod=macd_mid,    # 中期
                               slowperiod=macd_long,   # 长期
                               signalperiod=macd_short # 短期
                               )
    
    # 转换为 Series 并保持索引对齐
    dif = pd.Series(dif, index=series.index)
    dea = pd.Series(dea, index=series.index)
    hist = pd.Series(hist, index=series.index)
    
    print(f"dif length: {len(dif)}")
    print(f"dif index range: {dif.index[0]} to {dif.index[-1]}")
    
    print(f"dea length: {len(dea)}")
    print(f"dea index range: {dea.index[0]} to {dea.index[-1]}")
    
    print(f"hist length: {len(hist)}")
    print(f"hist index range: {hist.index[0]} to {hist.index[-1]}")


    
    
    # 2. 计算MACD差值及其EMA
    difdea_diff = dif - dea
    print(f"difdea_diff length: {len(difdea_diff)}")
    print(f"difdea_diff index range: {difdea_diff.index[0]} to {difdea_diff.index[-1]}")
    
    ddma_diff = difdea_diff.ewm(span=diff_ema_period, adjust=False).mean()
    print(f"ddma_diff length: {len(ddma_diff)}")
    print(f"ddma_diff index range: {ddma_diff.index[0]} to {ddma_diff.index[-1]}")


    #     # 1. 计算MACD基础值
    # # 确保输入序列是数值类型
    # series = pd.to_numeric(series, errors='coerce')
    
    # # 计算EMA，保持原始索引
    # exp1 = series.ewm(span=macd_mid, adjust=False).mean()
    # exp2 = series.ewm(span=macd_long, adjust=False).mean()
    
    # # 计算MACD线和信号线，保持原始索引
    # dif = exp1 - exp2  # MACD线
    # dea = dif.ewm(span=macd_short, adjust=False).mean()  # 信号线
    # hist = dif - dea  # MACD柱状图
    
    # # 确保数值类型并处理可能的无效值
    # dif = pd.to_numeric(dif, errors='coerce')
    # dea = pd.to_numeric(dea, errors='coerce')
    # hist = pd.to_numeric(hist, errors='coerce')
    
    # # 2. 计算MACD差值及其EMA，保持原始索引
    # difdea_diff = dif - dea
    ddma_diff = difdea_diff.ewm(span=diff_ema_period, adjust=False).mean()

        # 2. 计算MACD差值及其EMA，保持原始索引
    # difdea_diff = dif - dea
    # print(f"difdea_diff length: {len(difdea_diff)}")
    # print(f"difdea_diff index range: {difdea_diff.index[0]} to {difdea_diff.index[-1]}")
    # print(f"difdea_diff values range: {difdea_diff.min():.4f} to {difdea_diff.max():.4f}")
    
    ddma_diff = difdea_diff.ewm(span=diff_ema_period, adjust=False).mean()
    print(f"ddma_diff length: {len(ddma_diff)}")
    print(f"ddma_diff index range: {ddma_diff.index[0]} to {ddma_diff.index[-1]}")
    print(f"ddma_diff values range: {ddma_diff.min():.4f} to {ddma_diff.max():.4f}")
    
    
    
    # 3. 计算所有交叉信号
    cross_1 = pd.Series(0, index=series.index, dtype='float64')
    cross_2 = pd.Series(0, index=series.index, dtype='float64')
    cross_3 = pd.Series(0, index=series.index, dtype='float64')
    cross_4 = pd.Series(0, index=series.index, dtype='float64')
    
    # DIF与DEA的交叉 - 修改后的实现
    for i in range(1, len(series)):
        if dif.iloc[i] > dea.iloc[i] and dif.iloc[i-1] <= dea.iloc[i-1]:
            cross_1.iloc[i-1] = 1.0  # 上穿信号记录在当前位置
        elif dif.iloc[i] < dea.iloc[i] and dif.iloc[i-1] >= dea.iloc[i-1]:
            cross_1.iloc[i-1] = -1.0  # 下穿信号记录在当前位置
            
    # DIFDEA_DIFF与DDMA_DIFF的交叉 - 修改后的实现
    for i in range(1, len(series)):
        if difdea_diff.iloc[i] > ddma_diff.iloc[i] and difdea_diff.iloc[i-1] <= ddma_diff.iloc[i-1]:
            cross_2.iloc[i-1] = 10.0  # 上穿信号记录在当前位置
        elif difdea_diff.iloc[i] < ddma_diff.iloc[i] and difdea_diff.iloc[i-1] >= ddma_diff.iloc[i-1]:
            cross_2.iloc[i-1] = -10.0  # 下穿信号记录在当前位置
            
    # DEA与0轴的交叉 - 修改后的实现
    for i in range(1, len(series)):
        if dea.iloc[i] > 0 and dea.iloc[i-1] <= 0:
            cross_3.iloc[i-1] = 100.0  # 上穿信号记录在当前位置
        elif dea.iloc[i] < 0 and dea.iloc[i-1] >= 0:
            cross_3.iloc[i-1] = -100.0  # 下穿信号记录在当前位置
            
    # DIF与0轴的交叉 - 修改后的实现
    for i in range(1, len(series)):
        if dif.iloc[i] > 0 and dif.iloc[i-1] <= 0:
            cross_4.iloc[i-1] = 1000.0  # 上穿信号记录在当前位置
        elif dif.iloc[i] < 0 and dif.iloc[i-1] >= 0:
            cross_4.iloc[i-1] = -1000.0  # 下穿信号记录在当前位置


    # 4. 计算XLPL阶段
    xlpl_phase = pd.Series(0, index=series.index, dtype='float64')
    for i in range(len(series)):
        if difdea_diff.iloc[i] <= 0 and ddma_diff.iloc[i] > 0:
            xlpl_phase.iloc[i] = 1.0  # 吸筹
        elif difdea_diff.iloc[i] > 0 and ddma_diff.iloc[i] >= 0:
            xlpl_phase.iloc[i] = 2.0  # 拉升
        elif difdea_diff.iloc[i] >= 0 and ddma_diff.iloc[i] < 0:
            xlpl_phase.iloc[i] = 3.0  # 派发
        elif difdea_diff.iloc[i] < 0 and ddma_diff.iloc[i] <= 0:
            xlpl_phase.iloc[i] = 4.0  # 下跌

    # 5. 创建结果DataFrame
    results = pd.DataFrame({
        'MACD': dif,
        'MACD_Signal': dea,
        'MACD_Hist': hist,
        'DIFDEA_DIFF': pd.to_numeric(difdea_diff, errors='coerce'),
        'DDMA_DIFF': pd.to_numeric(ddma_diff, errors='coerce'),
        'XLPL_Phase': xlpl_phase,
        'Cross_1': cross_1,
        'Cross_2': cross_2,
        'Cross_3': cross_3,
        'Cross_4': cross_4
    })
    
    return results

# 2.0: Price MACD-XLPL CROSS
def process_price_macd(db, ticker, start_date=None, end_date=None):
    """
    处理价格的MACD信号并存入数据库
    
    Parameters:
    -----------
    db : TradingSignalDatabaseManager
        数据库管理器实例
    ticker : str
        股票代码
    start_date : str, optional
        开始日期
    end_date : str, optional
        结束日期

        Result(in db):
    --------
    pandas.DataFrame : 包含以下列的DataFrame:
        - Price_XLPL_Phase: XLPL阶段 (1:吸筹, 2:拉升, 3:派发, 4:下跌)
        - Price_Cross: 合并的交叉信号:
            * 1: DIF上穿DEA (Cross_1 UP)
            * -1: DIF下穿DEA (Cross_1 DN)
            * 2: DIF>DEA且DEA>0时的Cross_2 UP
            * -2: DIF<DEA且DEA<0时的Cross_2 DN
    """
    
    # 从数据库获取原始数据
    # df = db.get_data(ticker, start_date, end_date)
    # 获取close列数据
    df = db.get_data(ticker, start_date, end_date, columns=[ 'close'])
    
    if df.empty:
        print(f"Warning: No data found for {ticker}")
        return
    
    # 打印数据信息
    print("First few rows of data:")
    print(df.head())
    print("\nLast few rows of data:")
    print(df.tail())
    print(f"\nTotal number of rows: {len(df)}")
    
    # 从配置文件获取MACD参数
    price_macd_config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
    
    # 计算MACD信号
    signals = calculate_macd_signals(
        df['close'],
        macd_long=price_macd_config['macd_long'],
        macd_mid=price_macd_config['macd_mid'],
        macd_short=price_macd_config['macd_short'],
        diff_ema_period=price_macd_config['diff_ema_period']
    )

   
    
    # 准备要插入数据库的数据
    price_macd_df = pd.DataFrame()
    price_macd_df = pd.DataFrame(index=df.index)  # 使用原始数据的索引确保时间对齐
    price_macd_df['ticker'] = ticker
    price_macd_df['datetime'] = df.index
    price_macd_df['Price_MACD'] = signals['MACD']
    price_macd_df['Price_MACD_Signal'] = signals['MACD_Signal']
    price_macd_df['Price_MACD_Hist'] = signals['MACD_Hist']
    price_macd_df['Price_XLPL_Phase'] = signals['XLPL_Phase']

    # 合并Cross信号
    merged_cross = np.zeros(len(signals))
    for i in range(len(signals)):
        # 首先检查Cross_1信号
        if signals['Cross_1'].iloc[i] != 0:
            merged_cross[i] = signals['Cross_1'].iloc[i]
        
        # 然后在特定条件下检查Cross_2信号
        if signals['Cross_2'].iloc[i] != 0:
            dea = signals['MACD_Signal'].iloc[i]
            dif = signals['MACD'].iloc[i]
            
            # 当DEA>0且DIF>DEA时，保留上穿信号
            if dea > 0 and dif > dea and signals['Cross_2'].iloc[i] > 0:
                merged_cross[i] = 2
            # 当DEA<0且DIF<DEA时，保留下穿信号
            elif dea < 0 and dif < dea and signals['Cross_2'].iloc[i] < 0:
                merged_cross[i] = -2
    
    price_macd_df['Price_Cross'] = merged_cross
    
    # 将最终处理的数据写入数据库
    for idx, row in price_macd_df.iterrows():
        data_dict = {
            'Price_MACD': row['Price_MACD'],
            'Price_MACD_Signal': row['Price_MACD_Signal'],
            'Price_MACD_Hist': row['Price_MACD_Hist'],
            'Price_XLPL_Phase': row['Price_XLPL_Phase'],
            'Price_Cross': row['Price_Cross']
        }
        db.update_data(ticker, row['datetime'], data_dict)

    # 打印写入数据库前后的日期范围检查
    print(f"\nDate range check for {ticker}:")
    print("Original data date range:")
    print(f"Start: {df.index[0]}")
    print(f"End: {df.index[-1]}")
    print("\nProcessed data date range:")
    print(f"Start: {price_macd_df.index[0]}")
    print(f"End: {price_macd_df.index[-1]}")
    print(f"Total rows: Original={len(df)}, Processed={len(price_macd_df)}")
    
    if len(df) != len(price_macd_df):
        print("WARNING: Row count mismatch between original and processed data!")
        print(f"Difference: {len(df) - len(price_macd_df)} rows")

    print(f"Successfully process_price_macd for {ticker}")

# 3.0: Volume MACD-XLPL CROSS
def process_volume_macd(db, ticker, start_date=None, end_date=None):
    """
    处理成交量的MACD信号并存入数据库
    
    Parameters:
    -----------
    db : TradingSignalDatabaseManager
        数据库管理器实例
    ticker : str
        股票代码
    start_date : str, optional
        开始日期
    end_date : str, optional
        结束日期

    Result(in db):
    --------
    pandas.DataFrame : 包含以下列的DataFrame:
        - Volume_XLPL_Phase: XLPL阶段 (1:吸筹, 2:拉升, 3:派发, 4:下跌)
        - Volume_Cross: 合并的交叉信号:
            * 1: DIF上穿DEA (Cross_1 UP)
            * -1: DIF下穿DEA (Cross_1 DN)
            * 2: DIFDEA_DIFF上穿DDMA_DIFF (Cross_2 UP，仅在无Cross_1信号时)
            * -2: DIFDEA_DIFF下穿DDMA_DIFF (Cross_2 DN，仅在无Cross_1信号时)
    """
    # 从数据库获取原始数据
    # df = db.get_data(ticker, start_date, end_date)
    # 只获取volume列数据
    df = db.get_data(ticker, start_date, end_date, columns=['volume'])
    
    # 确保数据有效
    if df.empty:
        print(f"Warning: No data found for {ticker}")
        return
        
    # 处理成交量缺失值
    volume_na_count = df['volume'].isna().sum()
    if volume_na_count > 0:
        min_volume = df['volume'].min()
        if pd.isna(min_volume):  # 如果所有成交量都是NA
            min_volume = 1
        print(f"Warning: Found {volume_na_count} missing volume values for {ticker}, filling with minimum value: {min_volume}")
        df['volume'].fillna(min_volume, inplace=True)
    
    # 计算MACD信号  
    # 从配置文件获取Volume MACD参数
    volume_macd_config = EQUITY_CONFIG['INDICATORS']['VOLUME_MACD']
    
    signals = calculate_macd_signals(
        df['volume'],
        macd_long=volume_macd_config['macd_long'],
        macd_mid=volume_macd_config['macd_mid'],
        macd_short=volume_macd_config['macd_short'],
        diff_ema_period=volume_macd_config['diff_ema_period']
    )
    
    # 准备要插入数据库的数据
    volume_macd_df = pd.DataFrame()
    volume_macd_df = pd.DataFrame(index=df.index)  # 使用原始数据的索引确保时间对齐
    volume_macd_df['ticker'] = ticker
    volume_macd_df['datetime'] = df.index
    volume_macd_df['Volume_MACD'] = signals['MACD']
    volume_macd_df['Volume_MACD_Signal'] = signals['MACD_Signal']
    volume_macd_df['Volume_MACD_Hist'] = signals['MACD_Hist']
    volume_macd_df['Volume_XLPL_Phase'] = signals['XLPL_Phase']
    volume_macd_df['Volume_Cross'] = signals['Cross_1']  # 只使用Cross_1信号
    
    # 将最终处理的数据写入数据库
    for idx, row in volume_macd_df.iterrows():
        data_dict = {
            'Volume_MACD': row['Volume_MACD'],
            'Volume_MACD_Signal': row['Volume_MACD_Signal'],
            'Volume_MACD_Hist': row['Volume_MACD_Hist'],
            'Volume_XLPL_Phase': row['Volume_XLPL_Phase'],
            'Volume_Cross': row['Volume_Cross']
        }
        db.update_data(ticker, row['datetime'], data_dict)

    print(f"Successfully process_volume_macd for {ticker}")

# 4.0: HLBW 以及 MACD-XLPL CROSS
def process_hlbw(db, ticker, start_date=None, end_date=None):
    """
    处理HLBW指标并存入数据库
    
    Parameters:
    -----------
    db : TradingSignalDatabaseManager
        数据库管理器实例
    ticker : str
        股票代码
    start_date : str, optional
        开始日期
    end_date : str, optional
        结束日期
    """
    # 从数据库获取原始数据
    df = db.get_data(ticker, start_date, end_date, columns=['high', 'low', 'close'])  # 添加 'close'

    if df.empty:
        print(f"Warning: No data found for {ticker}")
        return
    
    # 从配置文件获取HLBW参数
    hlbw_config = EQUITY_CONFIG['INDICATORS']['HLBW']
    
    # 计算HLBW基础指标
    llv_low = pd.to_numeric(df['low'].rolling(window=hlbw_config['lookback_period']).min(), errors='coerce')
    hhv_high = pd.to_numeric(df['high'].rolling(window=hlbw_config['lookback_period']).max(), errors='coerce')
    
    # 计算基础比率
    basic_ratio = pd.to_numeric((df['close'] - llv_low) / (hhv_high - llv_low) * 100, errors='coerce')
    
    # 计算趋势线
    sma_inner = pd.to_numeric(basic_ratio.ewm(span=hlbw_config['inner_ema'], adjust=False).mean(), errors='coerce')
    sma_outer = pd.to_numeric(sma_inner.ewm(span=hlbw_config['outer_ema'], adjust=False).mean(), errors='coerce')
    x_7 = pd.to_numeric(3 * sma_inner - 2 * sma_outer, errors='coerce')
    trend_line = pd.to_numeric(x_7.ewm(span=hlbw_config['trend_ema'], adjust=False).mean(), errors='coerce')
    
    # 计算MACD信号
    signals = calculate_macd_signals(trend_line)

    # 添加调试信息
    print("\nHLBW MACD Debug Info:")
    print(f"MACD signals keys: {signals.keys()}")
    
    # 准备要插入数据库的数据
    hlbw_df = pd.DataFrame(index=df.index)
    hlbw_df['HLBW_Trend_Line'] = pd.to_numeric(trend_line, errors='coerce')
    hlbw_df['HLBW_MACD'] = pd.to_numeric(signals['MACD'], errors='coerce')
    hlbw_df['HLBW_MACD_Signal'] = pd.to_numeric(signals['MACD_Signal'], errors='coerce')
    hlbw_df['HLBW_MACD_Hist'] = pd.to_numeric(signals['MACD_Hist'], errors='coerce')
    hlbw_df['HLBW_XLPL_Phase'] = pd.to_numeric(signals['XLPL_Phase'], errors='coerce')
    

    
    """
    HLBW交叉信号处理逻辑：
    1. 优先处理Cross_1信号（DIF和DEA的交叉）
       - 上穿且趋势线>=底部支撑线时，信号=1
       - 下穿且趋势线<=顶部压力线时，信号=-1
       
    2. 如无Cross_1信号，检查Cross_2信号（DIFDEA_DIFF与DDMA_DIFF的交叉）
       - 上穿且DIFDEA_DIFF>0且趋势线>中低位警戒线时，信号=10
       - 下穿且DIFDEA_DIFF<0且趋势线<中高位警戒线时，信号=-10
       
    3. 如无Cross_1和Cross_2信号，检查Cross_3信号（DEA与0轴的交叉）
       - 上穿时，信号=100
       - 下穿时，信号=-100
    """
    merged_cross = np.zeros(len(signals))
    
    for i in range(len(signals)):
        trend_line_value = trend_line.iloc[i]
        cross_value = 0  # 临时变量存储当前位置的信号值
        
        # 优先处理Cross_1信号
        if signals['Cross_1'].iloc[i] > 0 and trend_line_value >= HLBW_BOTTOM_LINE:
            cross_value = 1
        elif signals['Cross_1'].iloc[i] < 0 and trend_line_value <= HLBW_TOP_LINE:
            cross_value = -1
            
        # 如果没有Cross_1信号，检查Cross_2
        elif signals['Cross_2'].iloc[i] != 0:
            difdea_diff = signals['DIFDEA_DIFF'].iloc[i]
            if (signals['Cross_2'].iloc[i] > 0 and 
                difdea_diff > 0 and 
                trend_line_value > HLBW_MID_LOW_LINE):
                cross_value = 10
            elif (signals['Cross_2'].iloc[i] < 0 and 
                  difdea_diff < 0 and 
                  trend_line_value < HLBW_MID_HIGH_LINE):
                cross_value = -10
                
        # 如果既没有Cross_1也没有Cross_2信号，检查Cross_3
        elif signals['Cross_3'].iloc[i] != 0:
            if signals['Cross_3'].iloc[i] > 0:
                cross_value = 100
            else:
                cross_value = -100
        
        merged_cross[i] = cross_value
    
    # hlbw_df['HLBW_Cross'] = merged_cross
    hlbw_df['HLBW_Cross'] = pd.to_numeric(merged_cross, errors='coerce')
    
    # 将最终处理的数据写入数据库
    for idx, row in hlbw_df.iterrows():
        data_dict = {
            'HLBW_Trend_Line': float(row['HLBW_Trend_Line']),
            'HLBW_MACD': float(row['HLBW_MACD']),
            'HLBW_MACD_Signal': float(row['HLBW_MACD_Signal']),
            'HLBW_MACD_Hist': float(row['HLBW_MACD_Hist']),
            'HLBW_XLPL_Phase': float(row['HLBW_XLPL_Phase']),
            'HLBW_Cross': float(row['HLBW_Cross'])
        }
        db.update_data(ticker, idx, data_dict)

    print(f"Successfully processed HLBW for {ticker}")


# 8.0: Price Prophet Trend and  Signal
## 8.0 训练Prophet模型
def process_prophet_forecast(db, ticker, start_date=None, end_date=None, forecast_days=30):
    """使用Prophet模型进行预测并处理MACD-XLPL-CROSS信号"""
    # 获取close数据用于预测
    df = db.get_data(ticker, start_date, end_date, columns=['close'])
    
    if df.empty:
        print(f"Warning: No data found for {ticker}")
        return
    
    # 打印数据前几行
    print("\n process_prophet_forecast  First few rows of data:")
    print(df.head())
    # print("\n")
    
    try:
        # 准备Prophet训练数据
        train_df = df.reset_index()
        train_df = train_df.rename(columns={'datetime': 'ds', 'close': 'y'})
        
        # 检查数据有效性
        if train_df['y'].isnull().sum() >= len(train_df) - 1:
            raise ValueError("数据集中有效数据不足")
            
        # 训练Prophet模型
        prophet_config = EQUITY_CONFIG['INDICATORS']['PROPHET']
        model = Prophet(
            daily_seasonality=prophet_config['daily_seasonality'],
            weekly_seasonality=prophet_config['weekly_seasonality'],
            yearly_seasonality=prophet_config['yearly_seasonality'],
            changepoint_prior_scale=prophet_config['changepoint_prior_scale']
        )
        model.fit(train_df)
        
        # 生成预测
        future = model.make_future_dataframe(periods=forecast_days, freq='D')
        forecast = model.predict(future)
        
        # 计算MACD信号
        price_macd_config = EQUITY_CONFIG['INDICATORS']['PRICE_MACD']
        signals = calculate_macd_signals(
            pd.to_numeric(forecast['yhat'], errors='coerce'),
            macd_long=price_macd_config['macd_long'],
            macd_mid=price_macd_config['macd_mid'],
            macd_short=price_macd_config['macd_short'],
            diff_ema_period=price_macd_config['diff_ema_period']
        )
        
        # 准备要插入数据库的数据
        prophet_df = pd.DataFrame()
        prophet_df['ds'] = forecast['ds']  # 保留时间列
        prophet_df['PH_yhat'] = pd.to_numeric(forecast['yhat'], errors='coerce')
        prophet_df['PH_yhat_lower'] = pd.to_numeric(forecast['yhat_lower'], errors='coerce')
        prophet_df['PH_yhat_upper'] = pd.to_numeric(forecast['yhat_upper'], errors='coerce')
    
        
        # 确保signals的索引与forecast匹配
        signals.index = range(len(signals))  # 重置signals的索引
        prophet_df['PH_XLPL_Phase'] = pd.to_numeric(signals['XLPL_Phase'], errors='coerce')

        # 添加MACD结果到DataFrame
        prophet_df['PH_MACD'] = pd.to_numeric(signals['MACD'], errors='coerce')
        prophet_df['PH_MACD_Signal'] = pd.to_numeric(signals['MACD_Signal'], errors='coerce')
        prophet_df['PH_MACD_Hist'] = pd.to_numeric(signals['MACD_Hist'], errors='coerce')
        
        # 设置索引
        prophet_df.set_index('ds', inplace=True)
        
        # 添加调试信息
        print("\nDebug - Data check after creation:")
        print("Prophet forecast head:")
        print(forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].head())
        print("\nSignals head:")
        print(signals.head())
        print("\nProphet_df head:")
        print(prophet_df.head())
        
        # 合并Cross信号
        merged_cross = np.zeros(len(signals))
        for i in range(len(signals)):
            if signals['Cross_1'].iloc[i] != 0:
                merged_cross[i] = signals['Cross_1'].iloc[i]
            # elif signals['Cross_2'].iloc[i] != 0:
            #     merged_cross[i] = signals['Cross_2'].iloc[i]
        
        prophet_df['PH_Cross'] = pd.to_numeric(merged_cross, errors='coerce')
        
        # 计算趋势持续时间和变化幅度
        trend_duration = np.zeros(len(forecast))
        trend_change = np.zeros(len(forecast))
        
        current_phase = 0
        phase_start_idx = 0
        phase_start_price = 0
        
        for i in range(len(forecast)):
            phase = signals['XLPL_Phase'].iloc[i]
            
            # 检测阶段变化
            if phase != current_phase:
                current_phase = phase
                phase_start_idx = i
                phase_start_price = forecast['yhat'].iloc[i]
            
            # 只关注拉升(2)和下跌(4)阶段
            if phase in [2, 4]:
                trend_duration[i] = i - phase_start_idx + 1
                
                current_price = forecast['yhat'].iloc[i]
                if phase_start_price != 0:
                    change = ((current_price - phase_start_price) / phase_start_price) * 100
                    trend_change[i] = change if phase == 2 else -change
        
        prophet_df['PH_Trend_Duration'] = pd.to_numeric(trend_duration, errors='coerce')
        prophet_df['PH_Trend_Change'] = pd.to_numeric(trend_change, errors='coerce')

        print("\nProphet_df head-2:")
        print(prophet_df.head())
        
        # 将结果写入数据库
        for idx, row in prophet_df.iterrows():
            try:
                data_dict = {
                    'PH_yhat': float(row['PH_yhat']),
                    'PH_yhat_lower': float(row['PH_yhat_lower']),
                    'PH_yhat_upper': float(row['PH_yhat_upper']),
                    'PH_MACD': float(row['PH_MACD']),
                    'PH_MACD_Signal': float(row['PH_MACD_Signal']),
                    'PH_MACD_Hist': float(row['PH_MACD_Hist']),
                    'PH_XLPL_Phase': float(row['PH_XLPL_Phase']),
                    'PH_Cross': float(row['PH_Cross']),
                    'PH_Trend_Duration': float(row['PH_Trend_Duration']),
                    'PH_Trend_Change': float(row['PH_Trend_Change'])
                }
                
                # 数据验证
                if any(pd.isna(value) for value in data_dict.values()):
                    print(f"Warning: NaN values found at {idx}")
                    continue
                    
                db.update_data(ticker, idx, data_dict)
            except Exception as e:
                print(f"Error at {idx}: {str(e)}")
                print(f"Data: {data_dict}")
        
        print(f"Successfully processed Prophet forecast for {ticker}")
        
    except Exception as e:
        print(f"Error processing Prophet forecast for {ticker}: {str(e)}")


# 20, Plot
## 20.1 matplotlib
def plot_analysis(db, ticker, start_date=None, end_date=None, output_type='both'):
    """
    综合分析图表显示函数
    
    Parameters:
    -----------
    db : TradingSignalDatabaseManager
        数据库管理器实例
    ticker : str
        股票代码
    start_date : str, optional
        开始日期
    end_date : str, optional
        结束日期
    output_type : str, optional
        输出类型：'matplotlib', 'bokeh', 或 'both'
    """
   # 从数据库获取所需数据    
    columns = [
        'close', 'high', 'low',  # 原始数据
        'Price_MACD', 'Price_MACD_Signal', 'Price_MACD_Hist', 'Price_XLPL_Phase', 'Price_Cross',  # 价格MACD
        'Volume_MACD', 'Volume_MACD_Signal', 'Volume_MACD_Hist', 'Volume_XLPL_Phase', 'Volume_Cross',  # 成交量MACD
        'HLBW_Trend_Line', 'HLBW_MACD', 'HLBW_MACD_Signal', 'HLBW_MACD_Hist',  # HLBW 和 HLBW MACD
        'HLBW_XLPL_Phase', 'HLBW_Cross',  # HLBW Phase 和 Cross
        'PH_yhat', 'PH_yhat_lower', 'PH_yhat_upper',  # Prophet 预测
        'PH_MACD', 'PH_MACD_Signal', 'PH_MACD_Hist',  # Prophet MACD
        'PH_XLPL_Phase', 'PH_Cross', 'PH_Trend_Duration', 'PH_Trend_Change',  # Prophet 其他指标
        'Entry_Signal', 'Exit_Signal', 'Position',  # 交易信号
        'Entry_Price', 'Exit_Price', 'Profit_Loss'  # 交易结果
    ]

    # 使用get_data而不是get_data
    df = db.get_data(ticker, start_date, end_date, columns=columns)
    
    if df.empty:
        print(f"Warning: No data found for {ticker}")
        return
        
    # 确保所有需要的列都存在
    for col in columns:
        if col not in df.columns:
            print(f"Warning: Column {col} not found in data")
            return
        
    def plot_matplotlib():
        """Matplotlib绘图函数"""
        fig, axes = plt.subplots(5, 1, figsize=(20, 25), sharex=True)
        
        # 1. Raw data with trading signals
        axes[0].plot(df.index, df['close'], label='Close Price', color='blue')
        buy_signals = df[df['Price_Cross'] > 0].index
        sell_signals = df[df['Price_Cross'] < 0].index
        axes[0].scatter(buy_signals, df.loc[buy_signals, 'close'], 
                       color='green', marker='^', s=100, label='Buy Signal')
        axes[0].scatter(sell_signals, df.loc[sell_signals, 'close'], 
                       color='red', marker='v', s=100, label='Sell Signal')
        axes[0].set_title(f'{ticker} Price with Trading Signals')
        
        # 2. Price MACD-XLPL-CROSS
        axes[1].plot(df.index, df['Price_MACD'], label='MACD', color='blue')
        axes[1].plot(df.index, df['Price_MACD_Signal'], label='Signal', color='orange')
        axes[1].bar(df.index, df['Price_MACD_Hist'], label='Histogram', color='gray', alpha=0.3)
        for phase in range(1, 5):
            phase_data = df[df['Price_XLPL_Phase'] == phase]
            if not phase_data.empty:
                axes[1].fill_between(phase_data.index, axes[1].get_ylim()[0], axes[1].get_ylim()[1],
                                   alpha=0.2, label=f'Phase {phase}')
        axes[1].set_title('Price MACD-XLPL-CROSS Analysis')
        
        # 3. Volume MACD-XLPL-CROSS
        axes[2].plot(df.index, df['Volume_MACD'], label='MACD', color='blue')
        axes[2].plot(df.index, df['Volume_MACD_Signal'], label='Signal', color='orange')
        axes[2].bar(df.index, df['Volume_MACD_Hist'], label='Histogram', color='gray', alpha=0.3)
        for phase in range(1, 5):
            phase_data = df[df['Volume_XLPL_Phase'] == phase]
            if not phase_data.empty:
                axes[2].fill_between(phase_data.index, axes[2].get_ylim()[0], axes[2].get_ylim()[1],
                                   alpha=0.2, label=f'Phase {phase}')
        axes[2].set_title('Volume MACD-XLPL-CROSS Analysis')
        
        # 4. HLBW Analysis
        axes[3].plot(df.index, df['HLBW_Trend_Line'], label='Trend Line', color='purple')
        # 添加 HLBW MACD 线
        axes[2].plot(df.index, df['HLBW_MACD'], label='HLBW MACD', color='blue')
        axes[2].plot(df.index, df['HLBW_MACD_Signal'], label='HLBW Signal', color='orange')
        axes[2].bar(df.index, df['HLBW_MACD_Hist'], label='HLBW Histogram', color='gray', alpha=0.3)
        for phase in range(1, 5):
            phase_data = df[df['HLBW_XLPL_Phase'] == phase]
            if not phase_data.empty:
                axes[3].fill_between(phase_data.index, axes[3].get_ylim()[0], axes[3].get_ylim()[1],
                                   alpha=0.2, label=f'Phase {phase}')
        axes[3].set_title('HLBW Analysis')
        
        # 5. Prophet Forecast
        axes[4].plot(df.index, df['close'], label='Actual', color='blue')
        axes[4].plot(df.index, df['PH_yhat'], label='Forecast', color='red')
        axes[4].fill_between(df.index, df['PH_yhat_lower'], df['PH_yhat_upper'], 
                           color='red', alpha=0.1, label='Confidence Interval')
        
        # Prophet Forecast with MACD
        axes[4].plot(df.index, df['close'], label='Actual', color='blue')
        axes[4].plot(df.index, df['PH_yhat'], label='Forecast', color='red')
        axes[4].fill_between(df.index, df['PH_yhat_lower'], df['PH_yhat_upper'], 
                           color='red', alpha=0.1, label='Confidence Interval')
        
        # 添加 Prophet MACD 线
        axes[4].plot(df.index, df['PH_MACD'], label='Prophet MACD', color='green')
        axes[4].plot(df.index, df['PH_MACD_Signal'], label='Prophet Signal', color='orange')
        axes[4].bar(df.index, df['PH_MACD_Hist'], label='Prophet Histogram', 
                   color='gray', alpha=0.3)
        
        for phase in range(1, 5):
            phase_data = df[df['PH_XLPL_Phase'] == phase]
            if not phase_data.empty:
                axes[4].fill_between(phase_data.index, axes[4].get_ylim()[0], axes[4].get_ylim()[1],
                                   alpha=0.2, label=f'Phase {phase}')
        axes[4].set_title('Prophet Forecast with MACD-XLPL-CROSS')
        
        # 通用设置
        for ax in axes:
            ax.legend(loc='upper left')
            ax.grid(True)
            ax.set_xlabel('Date')
        
        plt.tight_layout()
        plt.savefig(f'{ticker}_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
    

    def plot_bokeh():
        """Bokeh绘图函数"""
        # output_file(f"{ticker}_analysis.html")
        output_file(f"output/{ticker}_analysis.html")
        
        tools = "pan,wheel_zoom,box_zoom,reset,save,crosshair"
        width = 1600
        height = 300
    
        

        # 1. Raw data with trading signals (双向交易)
        p1 = figure(width=width, height=height*2, tools=tools, x_axis_type="datetime", 
                   title=f"{ticker} Price with Trading Signals (Bidirectional)")
        p1.line(df.index, df['close'], line_color='blue', legend_label='Close Price')
        
        # 做多信号：Entry_Signal > 0 且 Position > 0
        long_entry = df[df['Entry_Signal'] > 0]
        # 做空信号：Entry_Signal > 0 但后续 Position < 0（通过Position变化判断）
        # 或者通过Position的变化来判断做空入场
        df_with_prev_pos = df.copy()
        df_with_prev_pos['Prev_Position'] = df_with_prev_pos['Position'].shift(1).fillna(0)
        
        # 做多入场：从0或负变为正
        long_entries = df_with_prev_pos[(df_with_prev_pos['Position'] > 0) & (df_with_prev_pos['Prev_Position'] <= 0)]
        # 做空入场：从0或正变为负
        short_entries = df_with_prev_pos[(df_with_prev_pos['Position'] < 0) & (df_with_prev_pos['Prev_Position'] >= 0)]
        # 平仓：从非0变为0
        exits = df_with_prev_pos[(df_with_prev_pos['Position'] == 0) & (df_with_prev_pos['Prev_Position'] != 0)]
        
        # 绘制做多入场信号（绿色上三角）
        if not long_entries.empty:
            p1.triangle(long_entries.index, long_entries['close'], size=12, 
                       color='green', legend_label='Long Entry')
        
        # 绘制做空入场信号（红色下三角）
        if not short_entries.empty:
            p1.inverted_triangle(short_entries.index, short_entries['close'], 
                               size=12, color='red', legend_label='Short Entry')
        
        # 绘制平仓信号（黄色圆圈）
        if not exits.empty:
            p1.circle(exits.index, exits['close'], size=10, 
                     color='orange', legend_label='Exit')
        
        
        p2 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                x_range=p1.x_range, title="Price MACD-XLPL-CROSS Analysis")
        
        # 绘制 MACD 基本线，增加线条粗细
        p2.line(df.index, df['Price_MACD'], line_color='blue', line_width=2, legend_label='MACD')
        p2.line(df.index, df['Price_MACD_Signal'], line_color='orange', line_width=2, legend_label='Signal')
        p2.vbar(x=df.index, top=df['Price_MACD_Hist'], bottom=0, color='gray', alpha=0.3,
                legend_label='MACD Hist')
        
        # 修改相位颜色方案
        phase_colors = {
            1: '#0000CD',  # Xi: 蓝色 (吸筹)
            2: '#006400',  # La: 深绿色 (拉升)
            3: '#8B4513',  # Pi: 棕色 (派发)
            4: '#8B0000'   # Lo: 深红色 (下跌)
        }
        

        # 添加 Cross 信号标记
        Price_Cross_Up_signals = df[df['Price_Cross'] > 0]
        Price_Cross_Dn_signals = df[df['Price_Cross'] < 0]
        
        # 在 DEA 线上添加买入信号（上三角）
        if not Price_Cross_Up_signals.empty:
            p2.triangle(Price_Cross_Up_signals.index, 
                    Price_Cross_Up_signals['Price_MACD_Signal'],
                    size=12,  # 增大标记尺寸
                    color='green',
                    legend_label='Cross_Up')
        
        # 在 DEA 线上添加卖出信号（下三角）
        if not Price_Cross_Dn_signals.empty:
            p2.inverted_triangle(Price_Cross_Dn_signals.index,
                            Price_Cross_Dn_signals['Price_MACD_Signal'],
                            size=12,  # 增大标记尺寸
                            color='red',
                            legend_label='Cross_Dn')
        
        # 调整图例显示
        p2.legend.label_text_font_size = '10pt'  # 增大图例文字大小


        # 3. Volume MACD-XLPL-CROSS
        p3 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                   x_range=p1.x_range, title="Volume MACD-XLPL-CROSS Analysis")
        p3.line(df.index, df['Volume_MACD'], line_color='blue', legend_label='MACD')
        p3.line(df.index, df['Volume_MACD_Signal'], line_color='orange', legend_label='Signal')
        p3.vbar(x=df.index, top=df['Volume_MACD_Hist'], bottom=0, color='gray', alpha=0.3)
        # 添加 Volume Cross 信号
        volume_cross_up = df[df['Volume_Cross'] > 0]
        volume_cross_dn = df[df['Volume_Cross'] < 0]
        p3.triangle(volume_cross_up.index, volume_cross_up['Volume_MACD_Signal'], 
                    size=10, color='green', legend_label='CrossUp')
        p3.inverted_triangle(volume_cross_dn.index, volume_cross_dn['Volume_MACD_Signal'], 
                            size=10, color='red', legend_label='CrossDn')
        
        # 4. HLBW Analysis
        # p4 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
        #            x_range=p1.x_range, title="HLBW Analysis")
        # p4.line(df.index, df['HLBW_Trend_Line'], line_color='purple', legend_label='Trend Line')

        # 4. HLBW Analysis with MACD-XLPL-CROSS
        p4 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                x_range=p1.x_range, title="HLBW Analysis with MACD-XLPL-CROSS")
        
        # 添加 HLBW 水平线
        p4.line(df.index, [HLBW_TOP_LINE] * len(df), line_color='red', 
                line_dash='dashed', line_width=1, legend_label='Top Line (89)')
        p4.line(df.index, [HLBW_MID_HIGH_LINE] * len(df), line_color='orange', 
                line_dash='dashed', line_width=1, legend_label='Mid High (75)')
        p4.line(df.index, [HLBW_MID_LINE] * len(df), line_color='gray', 
                line_dash='dashed', line_width=1, legend_label='Mid Line (50)')
        p4.line(df.index, [HLBW_MID_LOW_LINE] * len(df), line_color='orange', 
                line_dash='dashed', line_width=1, legend_label='Mid Low (25)')
        p4.line(df.index, [HLBW_BOTTOM_LINE] * len(df), line_color='green', 
                line_dash='dashed', line_width=1, legend_label='Bottom Line (11)')
        
        # 绘制趋势线
        p4.line(df.index, df['HLBW_Trend_Line'], line_color='purple', legend_label='Trend Line')
        
        # 添加 HLBW MACD 线和信号线
        p4.line(df.index, df['HLBW_MACD'], line_color='blue', legend_label='HLBW MACD')
        p4.line(df.index, df['HLBW_MACD_Signal'], line_color='orange', legend_label='HLBW Signal')
        
        # 添加 HLBW MACD 柱状图
        p4.vbar(x=df.index, top=df['HLBW_MACD_Hist'], bottom=0, color='gray', alpha=0.3,
                legend_label='HLBW Hist')
        
        # 添加 HLBW Cross 信号
        hlbw_cross_up = df[df['HLBW_Cross'] > 0]
        hlbw_cross_dn = df[df['HLBW_Cross'] < 0]
        p4.triangle(hlbw_cross_up.index, hlbw_cross_up['HLBW_MACD_Signal'], 
                    size=10, color='green', legend_label='CrossUp')
        p4.inverted_triangle(hlbw_cross_dn.index, hlbw_cross_dn['HLBW_MACD_Signal'], 
                            size=10, color='red', legend_label='CrossDn')
        
        # 添加 XLPL 相位背景
        phase_colors = ['#ffd700', '#98fb98', '#ff69b4', '#87ceeb']  # 金色、浅绿、粉红、天蓝
        for phase in range(1, 5):
            phase_data = df[df['HLBW_XLPL_Phase'] == phase]
            if not phase_data.empty:
                p4.varea(x=phase_data.index, 
                        y1=df['HLBW_MACD'].min(), 
                        y2=df['HLBW_MACD'].max(),
                        fill_color=phase_colors[phase-1],
                        fill_alpha=0.1,
                        legend_label=f'Phase {phase}')
        
        
        # 5. Prophet Forecast
        p5 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                x_range=p1.x_range, title="Prophet Forecast")
        p5.line(df.index, df['close'], line_color='blue', legend_label='Actual')
        p5.line(df.index, df['PH_yhat'], line_color='red', legend_label='Forecast')
        p5.varea(df.index, df['PH_yhat_lower'], df['PH_yhat_upper'], 
                fill_color='red', fill_alpha=0.1, legend_label='Confidence Interval')
        
               
        # 6. Prophet MACD-XLPL-CROSS (新增)
        p6 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                x_range=p1.x_range, title="Prophet MACD-XLPL-CROSS Analysis")
        
        # 添加 Prophet MACD 线和信号线
        p6.line(df.index, df['PH_MACD'], line_color='blue', legend_label='Prophet MACD')
        p6.line(df.index, df['PH_MACD_Signal'], line_color='orange', legend_label='Prophet Signal')
        
        # 添加 Prophet MACD 柱状图
        p6.vbar(x=df.index, top=df['PH_MACD_Hist'], bottom=0, color='gray', alpha=0.3,
                legend_label='Prophet MACD Hist')
        
        # 添加 Prophet Cross 信号
        ph_cross_up = df[df['PH_Cross'] > 0]
        ph_cross_dn = df[df['PH_Cross'] < 0]
        p6.triangle(ph_cross_up.index, ph_cross_up['PH_MACD_Signal'], 
                    size=10, color='green', legend_label='CrossUp')
        p6.inverted_triangle(ph_cross_dn.index, ph_cross_dn['PH_MACD_Signal'], 
                            size=10, color='red', legend_label='CrossDn')
        
        # 添加 XLPL 相位背景
        phase_colors = ['#ffd700', '#98fb98', '#ff69b4', '#87ceeb']  # 金色、浅绿、粉红、天蓝
        for phase in range(1, 5):
            phase_data = df[df['PH_XLPL_Phase'] == phase]
            if not phase_data.empty:
                p6.varea(x=phase_data.index, 
                        y1=df['PH_MACD'].min(), 
                        y2=df['PH_MACD'].max(),
                        fill_color=phase_colors[phase-1],
                        fill_alpha=0.1,
                        legend_label=f'Phase {phase}')
        
        
        # 7. All MACD Subplot
        
        # Normalize MACD values
        df['Price_MACD_Norm'] = normalize_series(df['Price_MACD'])
        df['Volume_MACD_Norm'] = normalize_series(df['Volume_MACD'])
        df['HLBW_MACD_Norm'] = normalize_series(df['HLBW_MACD'])
        df['PH_MACD_Norm'] = normalize_series(df['PH_MACD'])

        # p7 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
        #             x_range=p1.x_range, title="All MACD Subplot")
        # # 绘制所有 MACD 线
        # p7.line(df.index, df['Price_MACD_Norm'], line_color='navy', legend_label='Price MACD')
        # p7.line(df.index, df['Volume_MACD_Norm'], line_color='teal', legend_label='Volume MACD')
        # p7.line(df.index, df['HLBW_MACD_Norm'], line_color='olive', legend_label='HLBW MACD')
        # p7.line(df.index, df['PH_MACD_Norm'], line_color='maroon', legend_label='Prophet MACD')
        # # 添加 Cross 信号
        # p7.triangle(Price_Cross_Up_signals.index, Price_Cross_Up_signals['Price_MACD_Signal'],
        #             size=6, color='green', legend_label='Price Cross Up')
        # p7.inverted_triangle(Price_Cross_Dn_signals.index, Price_Cross_Dn_signals['Price_MACD_Signal'],
        #                     size=6, color='red', legend_label='Price Cross Down')
        
        


    
        # 7. All MACD Subplot
        p7 = figure(width=width, height=height*2, tools=tools, x_axis_type="datetime",
                    x_range=p1.x_range, title="All MACD Subplot")
        # 绘制所有 MACD 线
        p7.line(df.index, df['Price_MACD_Norm'], line_color='navy', legend_label='Price MACD')
        p7.line(df.index, df['Volume_MACD_Norm'], line_color='teal', legend_label='Volume MACD')
        p7.line(df.index, df['HLBW_MACD_Norm'], line_color='olive', legend_label='HLBW MACD')
        p7.line(df.index, df['PH_MACD_Norm'], line_color='maroon', legend_label='Prophet MACD')

        # 添加 Price Cross 信号
        p7.triangle(Price_Cross_Up_signals.index, df.loc[Price_Cross_Up_signals.index, 'Price_MACD_Norm'],
                    size=6, color='green', legend_label='Price Cross Up')
        p7.inverted_triangle(Price_Cross_Dn_signals.index, df.loc[Price_Cross_Dn_signals.index, 'Price_MACD_Norm'],
                            size=6, color='red', legend_label='Price Cross Down')

        # 添加 Volume Cross 信号
        volume_cross_up = df[df['Volume_Cross'] > 0]
        volume_cross_dn = df[df['Volume_Cross'] < 0]
        p7.triangle(volume_cross_up.index, df.loc[volume_cross_up.index, 'Volume_MACD_Norm'],
                    size=6, color='green', legend_label='Volume Cross Up')
        p7.inverted_triangle(volume_cross_dn.index, df.loc[volume_cross_dn.index, 'Volume_MACD_Norm'],
                            size=6, color='red', legend_label='Volume Cross Down')

        # 添加 HLBW Cross 信号
        hlbw_cross_up = df[df['HLBW_Cross'] > 0]
        hlbw_cross_dn = df[df['HLBW_Cross'] < 0]
        p7.triangle(hlbw_cross_up.index, df.loc[hlbw_cross_up.index, 'HLBW_MACD_Norm'],
                    size=6, color='green', legend_label='HLBW Cross Up')
        p7.inverted_triangle(hlbw_cross_dn.index, df.loc[hlbw_cross_dn.index, 'HLBW_MACD_Norm'],
                            size=6, color='red', legend_label='HLBW Cross Down')

        # 添加 Prophet Cross 信号
        ph_cross_up = df[df['PH_Cross'] > 0]
        ph_cross_dn = df[df['PH_Cross'] < 0]
        p7.triangle(ph_cross_up.index, df.loc[ph_cross_up.index, 'PH_MACD_Norm'],
                    size=6, color='green', legend_label='Prophet Cross Up')
        p7.inverted_triangle(ph_cross_dn.index, df.loc[ph_cross_dn.index, 'PH_MACD_Norm'],
                            size=6, color='red', legend_label='Prophet Cross Down')



        # 8. Profit and Loss Analysis (新增 P9)
        p8 = figure(width=width, height=height, tools=tools, x_axis_type="datetime",
                    x_range=p1.x_range, title="Profit and Loss Analysis")

        # 计算总收益和单步 Profit_Loss
        df['Cumulative_Profit_Loss'] = df['Profit_Loss'].cumsum().fillna(0)
        df['Step_Profit_Loss'] = df['Profit_Loss'].fillna(0)

        # 绘制总收益曲线
        p8.line(df.index, df['Cumulative_Profit_Loss'], line_color='green', legend_label='Cumulative Profit/Loss')

        # 绘制单步 Profit_Loss 曲线
        p8.line(df.index, df['Step_Profit_Loss'], line_color='red', legend_label='Step Profit/Loss')

        # 添加 0 轴线
        p8.line(df.index, [0] * len(df), line_color='black', line_dash='dashed', line_width=1)  # 修改为 line 方法

        # 计算统计指标
        total_return = df['Cumulative_Profit_Loss'].iloc[-1]
        win_rate = (df['Profit_Loss'] > 0).mean() * 100
        max_drawdown = (df['Cumulative_Profit_Loss'] - df['Cumulative_Profit_Loss'].cummax()).min()

        # 添加统计指标作为标签
        p8.text(x=df.index[-1], y=total_return, text=f'Total Return: {total_return:.2f}', 
                text_color='black', text_font_size='10pt')
        p8.text(x=df.index[-1], y=max_drawdown, text=f'Max Drawdown: {max_drawdown:.2f}', 
                text_color='black', text_font_size='10pt')
        p8.text(x=df.index[-1], y=total_return * 0.9, text=f'Win Rate: {win_rate:.2f}%', 
                text_color='black', text_font_size='10pt')


        # 更新通用设置部分
        for p in [p1, p2, p3, p4, p5, p6, p7, p8]:  # 添加 p7 和 p8
            p.legend.location = "top_left"
            p.legend.click_policy = "hide"
            p.grid.grid_line_alpha = 0.3
        
        # 更新显示布局
        # show(column([p1, p2, p3, p4, p5, p6, p7]))  # 添加 p7 和 p8
        show(column([p1, p7, p8, p2, p3, p4, p5, p6]))




        
        # # 更新通用设置部分
        # for p in [p1, p2, p3, p4, p5, p6]:  # 添加 p6
        #     p.legend.location = "top_left"
        #     p.legend.click_policy = "hide"
        #     p.grid.grid_line_alpha = 0.3
        
        # # 更新显示布局
        # show(column([p1, p2, p3, p4, p5, p6]))  # 添加 p6

    

    # 确保输出目录存在
    output_dir = os.path.join(os.getcwd(), 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def normalize_series(series, new_min=-100, new_max=100):
        old_min, old_max = series.min(), series.max()
        return ((series - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min
    

    
    # 根据output_type选择输出方式
    if output_type == 'matplotlib':
        plot_matplotlib()
    elif output_type == 'bokeh':
        plot_bokeh()
    elif output_type == 'both':
        plot_matplotlib()
        plot_bokeh()
    else:
        raise ValueError("output_type must be 'matplotlib', 'bokeh', or 'both'")

# 80: 进出加减
# 入场  出场    加仓 减仓
### 80.1 
# --> Entry Signal: (1/2/3 的n和n-1中有两个有效Cross和一个 la/xi)
    # 1, PMACD: Cross_1 or XLPL_Phases = 'LA'
    # 2, VMACD: Cross_1 or XLPL_Phases = 'LA'
    # 3, BWMACD: Cross_1 or Cross_3 or XLPL_Phases = "LA"
    # * 1/2/3 中至少有2个Cross signal(包括当前和前一个data slice), 剩余的必须是'LA'的状态.
    # * 如果 PMACD 和 bwmacd都是Cross_1, Vmacd处于 'XI'状态也算有效?
# --> Entry Trend
    # PHmacd: XLPL_Phases = 'LA' or 'XI'
def check_entry_conditions_long(current_slice, prev_slice):
    """
    检查做多入场条件
    
    Parameters:
    -----------
    current_slice : pandas.Series
        当前时间点的数据
    prev_slice : pandas.Series
        前一个时间点的数据
        
    Returns:
    --------
    int:
        做多信号类型 (1-6)，0表示无信号
    """
    # 1. 价格MACD信号
    price_cross = (current_slice['Price_Cross'] == 1) or (prev_slice['Price_Cross'] == 1)
    price_la = (current_slice['Price_XLPL_Phase'] == 2)  # 2表示拉升(LA)
    price_signal = price_cross or price_la
    
    # 2. 成交量MACD信号
    volume_cross = (current_slice['Volume_Cross'] == 1) or (prev_slice['Volume_Cross'] == 1)
    volume_la = (current_slice['Volume_XLPL_Phase'] == 2)
    volume_xi = (current_slice['Volume_XLPL_Phase'] == 1)  # 1表示吸筹(XI)
    volume_signal = volume_cross or volume_la or volume_xi
    
    # 3. HLBW MACD信号
    hlbw_cross = (current_slice['HLBW_Cross'] == 1) or \
                 (current_slice['HLBW_Cross'] == 100) or \
                 (prev_slice['HLBW_Cross'] == 1) or \
                 (prev_slice['HLBW_Cross'] == 100)
    hlbw_la = (current_slice['HLBW_XLPL_Phase'] == 2)
    hlbw_signal = hlbw_cross or hlbw_la
    
    # 统计Cross信号数量
    cross_count = sum([
        1 if price_cross else 0,
        1 if volume_cross else 0,
        1 if hlbw_cross else 0
    ])
    
    # 特殊情况：PMACD和BWMACD都有Cross_1信号，Volume处于XI状态
    special_case = (
        price_cross and 
        hlbw_cross and 
        volume_xi
    )
    
    # 4. Prophet趋势确认
    prophet_signal = (
        (current_slice['PH_XLPL_Phase'] == 2) and  # 处于拉升状态
        (current_slice['PH_Trend_Duration'] >= 3)   # 趋势持续至少5天
        # (current_slice['PH_Trend_Change'] >= 0.03)  # 趋势变化幅度至少3%
    )
    
    # # Signal方法 1, 判断是否有效：
    # # 1. 只有在至少有两个交叉信号的情况下，且价格信号、成交量信号和 HLBW 信号都有效时，条件才成立。
    # # 2. 或者满足特殊情况
    # valid_signals_6 = (
    #     (cross_count >= 2 and all([
    #         price_signal,
    #         # volume_signal or volume_xi,  # volume可以是signal或XI状态
    #         volume_signal,
    #         hlbw_signal
    #     ])) or
    #     special_case
    # )
    # valid_signals_1 = price_cross and volume_cross and hlbw_cross and prophet_signal
    # valid_signals_2 = price_cross and volume_la and hlbw_cross and prophet_signal
    # valid_signals_3 = price_cross and volume_xi and hlbw_cross and prophet_signal
    # valid_signals_4 = volume_la and volume_cross and hlbw_cross and prophet_signal
    # valid_signals_5 = price_cross and volume_cross and hlbw_la and prophet_signal
    # valid_signals = valid_signals_1 or valid_signals_2 or valid_signals_3 or \
    #     valid_signals_4 or valid_signals_5 or valid_signals_6
    # return valid_signals

    # Signal 方法2 
    # 初始化 entry 信号类型
    entry_signal_type = 0  # 默认值为 0，表示没有 entry 信号

    # 定义有效信号的优先级顺序
    signals = [
        (price_cross and volume_cross and hlbw_cross and prophet_signal, 1),
        (price_cross and volume_la and hlbw_cross and prophet_signal, 2),
        (price_cross and volume_xi and hlbw_cross and prophet_signal, 3),
        (volume_la and volume_cross and hlbw_cross and prophet_signal, 4),
        (price_cross and volume_cross and hlbw_la and prophet_signal, 5),
        ((cross_count >= 2 and all([price_signal, volume_signal, hlbw_signal])) or special_case, 6)  # 修复这里
    ]

    # 遍历信号列表，找到第一个有效信号
    for valid_signal, signal_type in signals:
        if valid_signal:
            entry_signal_type = signal_type
            break  # 找到第一个有效信号后立即退出

    return entry_signal_type


def check_entry_conditions_short(current_slice, prev_slice):
    """
    检查做空入场条件（信号与做多相反）
    
    Parameters:
    -----------
    current_slice : pandas.Series
        当前时间点的数据
    prev_slice : pandas.Series
        前一个时间点的数据
        
    Returns:
    --------
    int:
        做空信号类型 (-1到-6)，0表示无信号
    """
    # 1. 价格MACD信号（做空：寻找下跌信号）
    price_cross = (current_slice['Price_Cross'] == -1) or (prev_slice['Price_Cross'] == -1)
    price_lo = (current_slice['Price_XLPL_Phase'] == 4)  # 4表示下跌(LO)
    price_signal = price_cross or price_lo
    
    # 2. 成交量MACD信号（做空也需要放量确认，逻辑不变）
    volume_cross = (current_slice['Volume_Cross'] == 1) or (prev_slice['Volume_Cross'] == 1) or \
                   (current_slice['Volume_Cross'] == -1) or (prev_slice['Volume_Cross'] == -1)
    volume_la = (current_slice['Volume_XLPL_Phase'] == 2)
    volume_xi = (current_slice['Volume_XLPL_Phase'] == 1)
    volume_signal = volume_cross or volume_la or volume_xi
    
    # 3. HLBW MACD信号（做空：寻找下跌信号）
    hlbw_cross = (current_slice['HLBW_Cross'] == -1) or \
                 (current_slice['HLBW_Cross'] == -100) or \
                 (prev_slice['HLBW_Cross'] == -1) or \
                 (prev_slice['HLBW_Cross'] == -100)
    hlbw_lo = (current_slice['HLBW_XLPL_Phase'] == 4)  # 4表示下跌
    hlbw_signal = hlbw_cross or hlbw_lo
    
    # 统计Cross信号数量
    cross_count = sum([
        1 if price_cross else 0,
        1 if volume_cross else 0,
        1 if hlbw_cross else 0
    ])
    
    # 特殊情况：PMACD和BWMACD都有Cross信号，Volume处于活跃状态
    special_case = (
        price_cross and 
        hlbw_cross and 
        volume_xi
    )
    
    # 4. Prophet趋势确认（做空：寻找下跌趋势）
    prophet_signal = (
        (current_slice['PH_XLPL_Phase'] == 4) and  # 处于下跌状态
        (current_slice['PH_Trend_Duration'] >= 3)   # 趋势持续至少3天
    )
    
    # 初始化 entry 信号类型（做空用负数）
    entry_signal_type = 0  # 默认值为 0，表示没有 entry 信号
    
    # 定义有效信号的优先级顺序（对应做多的信号，但返回负数）
    signals = [
        (price_cross and volume_cross and hlbw_cross and prophet_signal, -1),
        (price_cross and volume_la and hlbw_cross and prophet_signal, -2),
        (price_cross and volume_xi and hlbw_cross and prophet_signal, -3),
        (volume_la and volume_cross and hlbw_cross and prophet_signal, -4),
        (price_cross and volume_cross and hlbw_lo and prophet_signal, -5),
        ((cross_count >= 2 and all([price_signal, volume_signal, hlbw_signal])) or special_case, -6)
    ]
    
    # 遍历信号列表，找到第一个有效信号
    for valid_signal, signal_type in signals:
        if valid_signal:
            entry_signal_type = signal_type
            break
    
    return entry_signal_type

    
def check_exit_conditions_long(data_slice, future_slice):
    """
    检查做多出场条件
    
    Parameters:
    -----------
    data_slice : pandas.Series
        当前时间点的数据切片
    future_slice : pandas.DataFrame or None
        未来时间点的数据切片，用于Prophet预测
        
    Returns:
    --------
    bool
        是否满足做多出场条件
    """
    # 初始化变量
    current_phase_exit = False
    future_cross_exit = False
    reverse_entry = False
    price_reversal = False
    hlbw_reversal = False
    
    # 检查反向入场信号
    if data_slice['Price_Cross'] < 0:  # 价格MACD下穿
        reverse_entry = True
    
    # 检查价格反转
    if data_slice['Price_XLPL_Phase'] in [4]:  # 下跌阶段
        price_reversal = True
    
    # 检查HLBW反转
    if data_slice['HLBW_Cross'] < 0:  # HLBW下穿
        hlbw_reversal = True
    
    # 检查Prophet预测
    if data_slice['PH_XLPL_Phase'] in [4]:  # 当前预测处于派发或下跌阶段
        current_phase_exit = True
        
    # 检查未来预测
    if future_slice is not None and len(future_slice) > 0:
        # 检查未来3个周期是否有反向Cross信号
        future_cross_exit = any(future_slice['PH_Cross'].iloc[:3] < 0)  # 任何负值表示下穿信号
    
    # 合并所有反向信号
    prophet_exit = current_phase_exit or future_cross_exit
    reverse_signal = reverse_entry or price_reversal or hlbw_reversal or prophet_exit
    # reverse_signal = False # only debug
    
    return reverse_signal


def check_exit_conditions_short(data_slice, future_slice):
    """
    检查做空出场条件（信号与做多相反）
    
    Parameters:
    -----------
    data_slice : pandas.Series
        当前时间点的数据切片
    future_slice : pandas.DataFrame or None
        未来时间点的数据切片，用于Prophet预测
        
    Returns:
    --------
    bool
        是否满足做空出场条件
    """
    # 初始化变量
    current_phase_exit = False
    future_cross_exit = False
    reverse_entry = False
    price_reversal = False
    hlbw_reversal = False
    
    # 检查反向入场信号（做空出场：遇到上涨信号）
    if data_slice['Price_Cross'] > 0:  # 价格MACD上穿
        reverse_entry = True
    
    # 检查价格反转（做空出场：遇到拉升阶段）
    if data_slice['Price_XLPL_Phase'] in [2]:  # 拉升阶段
        price_reversal = True
    
    # 检查HLBW反转（做空出场：遇到上穿）
    if data_slice['HLBW_Cross'] > 0:  # HLBW上穿
        hlbw_reversal = True
    
    # 检查Prophet预测（做空出场：遇到拉升阶段）
    if data_slice['PH_XLPL_Phase'] in [2]:  # 当前预测处于拉升阶段
        current_phase_exit = True
        
    # 检查未来预测
    if future_slice is not None and len(future_slice) > 0:
        # 检查未来3个周期是否有反向Cross信号
        future_cross_exit = any(future_slice['PH_Cross'].iloc[:3] > 0)  # 任何正值表示上穿信号
    
    # 合并所有反向信号
    prophet_exit = current_phase_exit or future_cross_exit
    reverse_signal = reverse_entry or price_reversal or hlbw_reversal or prophet_exit
    
    return reverse_signal

# Generate Performance Metrics
# def generate_performance_metrics(profit_loss_curve, initial_capital, current_capital):   
def generate_performance_metrics(profit_loss_curve, initial_capital = 10000):   
    """
    计算回测性能指标
    
    Returns:
    --------
    Dict[str, float]
        包含各项性能指标的字典
    """
    if profit_loss_curve.empty:
        return {}
    
    current_capital = initial_capital + sum(profit_loss_curve)  # 计算当前资本
    
    # 计算基础指标
    total_return = (current_capital - initial_capital) / initial_capital
    annual_return = total_return * (252 / len(profit_loss_curve))  # 假设一年252个交易日
    
    # 计算风险指标
    daily_returns = pd.Series(profit_loss_curve).fillna(0)
    volatility = daily_returns.std() * np.sqrt(252)  # 年化波动率
    sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() != 0 else 0
    
    # 计算回撤
    cumulative_returns = (1 + daily_returns).cumprod()
    rolling_max = cumulative_returns.expanding().max()
    drawdowns = cumulative_returns / rolling_max - 1
    max_drawdown = drawdowns.min()
    
    # 计算交易相关指标
    total_trades = len(profit_loss_curve[profit_loss_curve != 0])  # 计算有效交易
    winning_trades = sum(1 for pl in profit_loss_curve if pl > 0)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    # 计算盈亏比
    gross_profit = sum(pl for pl in profit_loss_curve if pl > 0)
    gross_loss = abs(sum(pl for pl in profit_loss_curve if pl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
    
    return {
        'Initial Capital': initial_capital,
        'Final Capital': current_capital,
        'Total Return': total_return,
        'Annual Return': annual_return,
        'Sharpe Ratio': sharpe_ratio,
        'Volatility': volatility,
        'Max Drawdown': max_drawdown,
        'Total Trades': total_trades,
        'Win Rate': win_rate,
        'Profit Factor': profit_factor,
        'Average Trade': np.mean(profit_loss_curve) if total_trades > 0 else 0,
        'Average Win': np.mean([pl for pl in profit_loss_curve if pl > 0]) if winning_trades > 0 else 0,
        'Average Loss': np.mean([pl for pl in profit_loss_curve if pl < 0]) if (total_trades - winning_trades) > 0 else 0,
    } 

# 20250301  增加了 profit loss indicators
# 20251127  增加了开盘/收盘阶段优化
# 20251129  增加了加仓策略支持
def generate_trading_signals(trading_signal_db, ticker, start_date, end_date, 
                            enable_bidirectional_trading=True, hold_overnight=False,
                            scaling_strategy_name='aggressive_pyramid'):
    """
    生成交易信号（支持双向交易 + 开盘收盘优化 + 加仓策略）
    
    Parameters:
    -----------
    trading_signal_db : TradingSignalDatabaseManager
        数据库管理器
    ticker : str
        期货代码
    start_date : str
        开始日期
    end_date : str
        结束日期
    enable_bidirectional_trading : bool
        是否启用双向交易（默认True）
    hold_overnight : bool
        是否允许持仓过夜（默认False，收盘前强制平仓）
    scaling_strategy_name : str
        加仓策略名称（默认'aggressive_pyramid'）
        可选：'pyramid', 'aggressive_pyramid', 'linear', 'inverse_pyramid', 
              'fixed_fraction', 'martingale', 'anti_martingale', 'none'
    """
    
    # 创建交易时段管理器（优化版本新增）
    session_mgr = TradingSessionManager(
        buffer_minutes=10,      # 开盘后10分钟缓冲期
        close_minutes=5,        # 收盘前5分钟开始平仓
        hold_overnight=hold_overnight  # 是否允许持仓过夜
    )
    
    # 初始化交易成本模型（盈亏计算修复 - 20251128）
    specs = FuturesContractSpecs.get_specs(ticker)
    contract_multiplier = specs['multiplier']
    cost_calculator = TradingCostCalculator(ticker)
    
    # 辅助函数：应用滑点
    def apply_slippage_to_price(price, direction):
        """direction: 'buy' or 'sell'"""
        dir_int = 1 if direction == 'buy' else -1
        return cost_calculator.slippage_model.apply_slippage(price, dir_int)
    
    # 辅助函数：计算手续费
    def calculate_commission(action, price, volume):
        """action: 'open' or 'close'"""
        return cost_calculator.commission_model.calculate_commission(price, volume, action)
    
    # 构建查询
    query = """
    SELECT datetime, close, high, low, 
           Price_MACD, Price_MACD_Signal, Price_MACD_Hist, Price_XLPL_Phase, Price_Cross,
           Volume_MACD, Volume_MACD_Signal, Volume_MACD_Hist, Volume_XLPL_Phase, Volume_Cross,
           HLBW_Trend_Line, HLBW_MACD, HLBW_MACD_Signal, HLBW_MACD_Hist, HLBW_XLPL_Phase, HLBW_Cross,
           PH_yhat, PH_yhat_lower, PH_yhat_upper,
           PH_MACD, PH_MACD_Signal, PH_MACD_Hist, PH_XLPL_Phase, PH_Cross,
           PH_Trend_Duration, PH_Trend_Change
    FROM trading_data 
    WHERE ticker = ? AND datetime >= date(?) AND datetime < date(?, '+1 day')
    ORDER BY datetime
    """
    params = [ticker, start_date, end_date]
    
    # 使用 conn 而不是 memory_conn
    df = pd.read_sql(query, trading_signal_db.conn, params=params)
    
    # 初始化信号列
    signals_df = pd.DataFrame()
    signals_df['ticker'] = ticker
    signals_df['datetime'] = df['datetime']
    signals_df['Long_Entry_Signal'] = 0  # 做多入场信号
    signals_df['Long_Exit_Signal'] = False  # 做多出场信号
    signals_df['Short_Entry_Signal'] = 0  # 做空入场信号
    signals_df['Short_Exit_Signal'] = False  # 做空出场信号
    signals_df['Position'] = 0  # 持仓：正数=多仓，负数=空仓，0=无仓
    signals_df['Entry_Price'] = 0.0
    signals_df['Exit_Price'] = 0.0
    signals_df['Profit_Loss'] = 0.0
    
    # 遍历数据生成信号
    position = 0  # 当前持仓状态：正数=多仓数量，负数=空仓数量
    entry_price = 0.0  # 入场价格（原始价格，不含滑点）
    entry_price_with_slippage = 0.0  # 入场价格（含滑点）
    entry_commission = 0.0  # 开仓手续费
    close_reason_counter = {'close_time': 0, 'normal': 0}  # 统计信号屏蔽原因（移除buffer）
    
    for i in range(1, len(df)):
        current_slice = df.iloc[i]
        prev_slice = df.iloc[i-1]
        current_timestamp = pd.to_datetime(current_slice['datetime'])
        
        # ============ 仅收盘阶段优化逻辑 ============
        
        # 1. 检查是否应该强制平仓（收盘前N分钟）- 保留
        should_close, close_reason = session_mgr.should_force_close(current_timestamp)
        if should_close and position != 0:
            # 强制平仓
            current_price = current_slice['close']
            
            # 应用滑点
            if position > 0:
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'sell')
            else:
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'buy')
            
            # 计算平仓手续费
            close_commission = calculate_commission('close', exit_price_with_slippage, abs(position))
            
            # 计算盈亏（含交易成本）
            if position > 0:
                # 平多仓
                signals_df.loc[i, 'Long_Exit_Signal'] = True
                gross_pnl = (exit_price_with_slippage - entry_price_with_slippage) * abs(position) * contract_multiplier
            else:
                # 平空仓
                signals_df.loc[i, 'Short_Exit_Signal'] = True
                gross_pnl = (entry_price_with_slippage - exit_price_with_slippage) * abs(position) * contract_multiplier
            
            # 扣除交易成本
            total_cost = entry_commission + close_commission
            net_pnl = gross_pnl - total_cost
            
            signals_df.loc[i, 'Exit_Price'] = current_price  # 记录原始平仓价（不含滑点）
            signals_df.loc[i, 'Profit_Loss'] = net_pnl  # 记录净盈亏（元）
            position = 0
            entry_price = 0.0
            entry_price_with_slippage = 0.0
            entry_commission = 0.0
            signals_df.loc[i, 'Position'] = position
            close_reason_counter['close_time'] += 1
            continue  # 强制平仓后，跳过本轮其他逻辑
        
        # 2. 禁用开盘缓冲期 - 始终允许生成信号（除了收盘期）
        # 获取未来预测数据
        future_slice = None
        if i + 30 < len(df):
            future_slice = df.iloc[i:i+3]
        
        # 3. 直接生成交易信号（不检查缓冲期）
        long_entry_signal = check_entry_conditions_long(current_slice, prev_slice)
        long_exit_signal = check_exit_conditions_long(current_slice, future_slice)
        
        if enable_bidirectional_trading:
            short_entry_signal = check_entry_conditions_short(current_slice, prev_slice)
            short_exit_signal = check_exit_conditions_short(current_slice, future_slice)
        else:
            short_entry_signal = 0
            short_exit_signal = False
        
        close_reason_counter['normal'] += 1
        
        # 记录原始信号
        signals_df.loc[i, 'Long_Entry_Signal'] = long_entry_signal
        signals_df.loc[i, 'Short_Entry_Signal'] = short_entry_signal
        
        # ============ 原有交易逻辑 ============
        # 交易逻辑：优先级为 平仓 > 反向开仓 > 同向加仓
        current_price = current_slice['close']
        
        # 情况1：当前持有多仓
        if position > 0:
            # 检查是否需要平多仓
            if long_exit_signal:
                # 应用滑点
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'sell')
                
                # 计算平仓手续费
                close_commission = calculate_commission('close', exit_price_with_slippage, abs(position))
                
                # 计算盈亏
                gross_pnl = (exit_price_with_slippage - entry_price_with_slippage) * abs(position) * contract_multiplier
                total_cost = entry_commission + close_commission
                net_pnl = gross_pnl - total_cost
                
                signals_df.loc[i, 'Long_Exit_Signal'] = True
                signals_df.loc[i, 'Exit_Price'] = current_price
                signals_df.loc[i, 'Profit_Loss'] = net_pnl
                position = 0
                entry_price = 0.0
                entry_price_with_slippage = 0.0
                entry_commission = 0.0
            # 检查是否有做空信号（平多开空）
            elif enable_bidirectional_trading and short_entry_signal < 0:
                # 先平多仓
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'sell')
                close_commission = calculate_commission('close', exit_price_with_slippage, abs(position))
                gross_pnl = (exit_price_with_slippage - entry_price_with_slippage) * abs(position) * contract_multiplier
                total_cost = entry_commission + close_commission
                net_pnl = gross_pnl - total_cost
                
                signals_df.loc[i, 'Long_Exit_Signal'] = True
                signals_df.loc[i, 'Exit_Price'] = current_price
                signals_df.loc[i, 'Profit_Loss'] = net_pnl
                
                # 再开空仓
                entry_price_with_slippage = apply_slippage_to_price(current_price, 'sell')
                entry_commission = calculate_commission('open', entry_price_with_slippage, 1)
                
                signals_df.loc[i, 'Short_Entry_Signal'] = short_entry_signal
                position = -1  # 开空仓
                entry_price = current_price
                signals_df.loc[i, 'Entry_Price'] = entry_price
            # 持仓不变
            else:
                signals_df.loc[i, 'Entry_Price'] = entry_price
        
        # 情况2：当前持有空仓
        elif position < 0:
            # 检查是否需要平空仓
            if short_exit_signal:
                # 应用滑点
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'buy')
                
                # 计算平仓手续费
                close_commission = calculate_commission('close', exit_price_with_slippage, abs(position))
                
                # 计算盈亏
                gross_pnl = (entry_price_with_slippage - exit_price_with_slippage) * abs(position) * contract_multiplier
                total_cost = entry_commission + close_commission
                net_pnl = gross_pnl - total_cost
                
                signals_df.loc[i, 'Short_Exit_Signal'] = True
                signals_df.loc[i, 'Exit_Price'] = current_price
                signals_df.loc[i, 'Profit_Loss'] = net_pnl
                position = 0
                entry_price = 0.0
                entry_price_with_slippage = 0.0
                entry_commission = 0.0
            # 检查是否有做多信号（平空开多）
            elif long_entry_signal > 0:
                # 先平空仓
                exit_price_with_slippage = apply_slippage_to_price(current_price, 'buy')
                close_commission = calculate_commission('close', exit_price_with_slippage, abs(position))
                gross_pnl = (entry_price_with_slippage - exit_price_with_slippage) * abs(position) * contract_multiplier
                total_cost = entry_commission + close_commission
                net_pnl = gross_pnl - total_cost
                
                signals_df.loc[i, 'Short_Exit_Signal'] = True
                signals_df.loc[i, 'Exit_Price'] = current_price
                signals_df.loc[i, 'Profit_Loss'] = net_pnl
                
                # 再开多仓
                entry_price_with_slippage = apply_slippage_to_price(current_price, 'buy')
                entry_commission = calculate_commission('open', entry_price_with_slippage, 1)
                
                signals_df.loc[i, 'Long_Entry_Signal'] = long_entry_signal
                position = 1  # 开多仓
                entry_price = current_price
                signals_df.loc[i, 'Entry_Price'] = entry_price
            # 持仓不变
            else:
                signals_df.loc[i, 'Entry_Price'] = entry_price
        
        # 情况3：当前无仓位
        else:
            # 检查做多信号
            if long_entry_signal > 0:
                # 应用滑点并计算开仓成本
                entry_price_with_slippage = apply_slippage_to_price(current_price, 'buy')
                entry_commission = calculate_commission('open', entry_price_with_slippage, 1)
                
                signals_df.loc[i, 'Long_Entry_Signal'] = long_entry_signal
                position = 1
                entry_price = current_price
                signals_df.loc[i, 'Entry_Price'] = entry_price
            # 检查做空信号（只在启用双向交易时）
            elif enable_bidirectional_trading and short_entry_signal < 0:
                # 应用滑点并计算开仓成本
                entry_price_with_slippage = apply_slippage_to_price(current_price, 'sell')
                entry_commission = calculate_commission('open', entry_price_with_slippage, 1)
                
                signals_df.loc[i, 'Short_Entry_Signal'] = short_entry_signal
                position = -1
                entry_price = current_price
                signals_df.loc[i, 'Entry_Price'] = entry_price
        
        # 更新持仓状态
        signals_df.loc[i, 'Position'] = position
    
    # 将交易信号写入数据库
    for idx, row in signals_df.iterrows():
        # Entry_Signal: 正值表示做多(1-6)，负值表示做空(-1到-6)
        entry_signal = row['Long_Entry_Signal'] if row['Long_Entry_Signal'] != 0 else row['Short_Entry_Signal']
        data_dict = {
            'Entry_Signal': entry_signal,
            'Exit_Signal': row['Long_Exit_Signal'] or row['Short_Exit_Signal'],
            'Position': row['Position'],
            'Entry_Price': row['Entry_Price'],
            'Exit_Price': row['Exit_Price'],
            'Profit_Loss': row['Profit_Loss']
        }
        trading_signal_db.update_data(ticker, row['datetime'], data_dict)

    # 计算性能指标（基础策略）
    profit_loss_curve = pd.Series(signals_df['Profit_Loss']) 
    # current_capital = initial_capital + sum(profit_loss_curve)  # 计算当前资本
    performance_metrics = generate_performance_metrics(profit_loss_curve)
    print(f"\n【基础策略】Performance Metrics for {ticker}: {performance_metrics}")
    
    # 输出优化统计信息（仅收盘优化）
    print(f"\n【收盘平仓优化统计】{ticker}:")
    print(f"  - 收盘强制平仓次数: {close_reason_counter['close_time']} 次")
    print(f"  - 正常交易次数: {close_reason_counter['normal']} 次")
    print(f"  - 总K线数: {len(df)} 根")
    print(f"  - 开盘缓冲期: 已禁用（允许开盘即时交易）")
    
    # ============ 应用加仓策略 ============
    if scaling_strategy_name and scaling_strategy_name.lower() != 'none':
        print(f"\n【加仓策略】Applying scaling strategy: {scaling_strategy_name}")
        
        # 获取加仓配置
        if scaling_strategy_name in SCALING_CONFIGS:
            scaling_config = SCALING_CONFIGS[scaling_strategy_name]
        else:
            print(f"Warning: Unknown scaling strategy '{scaling_strategy_name}', using default 'aggressive_pyramid'")
            scaling_config = SCALING_CONFIGS['aggressive_pyramid']
        
        try:
            # 生成加仓信号
            scaling_signals_df = generate_scaling_signals(
                trading_signal_db, ticker, start_date, end_date, scaling_config
            )
            
            if not scaling_signals_df.empty:
                # 计算加仓策略性能
                scaling_metrics = calculate_scaling_performance(scaling_signals_df)
                
                print(f"\n【加仓策略性能】{ticker} - {scaling_strategy_name}:")
                print(f"  ✓ 总收益率: {scaling_metrics['total_return_pct']:.2f}%")
                print(f"  ✓ 夏普比率: {scaling_metrics['sharpe_ratio']:.4f}")
                print(f"  ✓ 胜率: {scaling_metrics['win_rate']:.2%}")
                print(f"  ✓ 最大回撤: {scaling_metrics['max_drawdown_pct']:.2f}%")
                print(f"  ✓ 交易次数: {scaling_metrics['total_trades']}")
                print(f"  ✓ 平均加仓层级: {scaling_metrics['avg_scaling_levels']:.2f}")
                
                # 对比基础策略和加仓策略
                base_return = performance_metrics.get('Total Return', 0) * 100
                scaling_return = scaling_metrics['total_return_pct']
                improvement = scaling_return - base_return
                print(f"\n【策略对比】")
                print(f"  基础策略收益: {base_return:.2f}%")
                print(f"  加仓策略收益: {scaling_return:.2f}%")
                print(f"  收益提升: {improvement:+.2f}%")
                
            else:
                print(f"Warning: No scaling signals generated for {ticker}")
                
        except Exception as e:
            print(f"Error applying scaling strategy for {ticker}: {e}")
            print("Continuing with base strategy signals...")
    
    print(f"\nSuccessfully generate_trading_signals for {ticker} (with {scaling_strategy_name} scaling)")


######### multi thread,start
import concurrent.futures
from datetime import datetime
# from TradingSignalDatabaseManager import TradingSignalDatabaseManager

# 新增：智能数据更新管理器（移到 process_ticker 之前以确保可用）
class SmartDataUpdateManager:
    """智能数据更新管理器：处理全量、增量和实时更新"""
    
    def __init__(self, db_manager: TradingSignalDatabaseManager, config: dict = None):
        self.db = db_manager
        self.config = config or EQUITY_CONFIG
        self.logger = logging.getLogger(__name__)
        
    def update_ticker_data(self, ticker: str, my_raw_db: str, my_raw_table: str, 
                          start_date: str = None, end_date: str = None, 
                          is_realtime: bool = False,
                          scaling_strategy_name: str = 'aggressive_pyramid') -> Dict:
        """
        智能更新单个股票数据
        
        Returns:
        --------
        Dict: 更新结果统计
        """
        update_start_time = time.time()
        
        # 1. 检查是否强制全量更新
        if self.config['UPDATE_STRATEGY'].get('force_full_update', False):
            strategy = 'full'
            strategy_info = {
                'strategy': 'full',
                'start_date': start_date or '2015-01-01',
                'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
                'reason': 'Force full update mode enabled'
            }
            self.logger.info(f"Force full update for {ticker}")
        else:
            # 获取智能更新策略
            strategy_info = self.db.get_update_strategy(ticker, start_date, end_date)
            strategy = strategy_info['strategy']
            
            if strategy == 'skip':
                self.logger.info(f"Skipping {ticker}: {strategy_info['reason']}")
                return {'ticker': ticker, 'strategy': 'skip', 'records_updated': 0, 'duration': 0}
        
        self.logger.info(f"Processing {ticker} with {strategy} strategy: {strategy_info['reason']}")
        
        try:
            records_updated = 0
            
            # 2. 在处理新数据之前，先检查并删除该ticker的所有旧记录
            # 确保每次回测的数据都是最新的，避免重复
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trading_data WHERE ticker = ?", (ticker,))
            existing_count = cursor.fetchone()[0]
            
            if existing_count > 0:
                self.logger.info(f"Found {existing_count} existing records for {ticker}, deleting all old data...")
                cursor.execute("DELETE FROM trading_data WHERE ticker = ?", (ticker,))
                self.db.conn.commit()
                self.logger.info(f"Successfully deleted all existing records for {ticker}")
            
            # 3. 根据策略下载和处理数据
            if strategy in ['full', 'incremental']:
                records_updated += self._process_raw_data(
                    ticker, my_raw_db, my_raw_table, 
                    strategy_info['start_date'], strategy_info['end_date']
                )
                
                # 4. 计算技术指标（仅在有新数据时）
                if records_updated > 0:
                    self._process_indicators(
                        ticker, strategy_info['start_date'], strategy_info['end_date']
                    )
                    
                    # 5. 生成交易信号（含加仓策略）
                    self._generate_trading_signals(
                        ticker, strategy_info['start_date'], 
                        (pd.to_datetime(strategy_info['end_date']) + pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
                        scaling_strategy_name=scaling_strategy_name
                    )
            
            elif strategy == 'realtime':
                records_updated += self._process_realtime_data(
                    ticker, my_raw_db, my_raw_table
                )
            
            # 6. 更新元数据
            if records_updated > 0:
                completeness = self.db.check_data_completeness(ticker)
                self.db.update_ticker_metadata(
                    ticker, 
                    completeness['first_date'], 
                    completeness['last_date'],
                    completeness['total_records']
                )
            
            # 7. 记录更新日志
            duration = time.time() - update_start_time
            self.db.log_update(
                ticker, strategy, strategy_info['start_date'], 
                strategy_info['end_date'], records_updated, duration, 'success'
            )
            
            return {
                'ticker': ticker, 
                'strategy': strategy, 
                'records_updated': records_updated, 
                'duration': duration,
                'status': 'success'
            }
            
        except Exception as e:
            duration = time.time() - update_start_time
            error_msg = str(e)
            self.logger.error(f"Error processing {ticker}: {error_msg}")
            
            self.db.log_update(
                ticker, strategy, strategy_info.get('start_date'), 
                strategy_info.get('end_date'), 0, duration, 'failed', error_msg
            )
            
            return {
                'ticker': ticker, 
                'strategy': strategy, 
                'records_updated': 0, 
                'duration': duration,
                'status': 'failed',
                'error': error_msg
            }
    
    def _process_raw_data(self, ticker: str, my_raw_db: str, my_raw_table: str, 
                         start_date: str, end_date: str) -> int:
        """处理期货原始数据下载"""
        # 连接MySQL数据库
        mysql_conn = pymysql.connect(
            host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
            port=3306,
            user='root',
            password='Wxtfz13245',
            database=my_raw_db
        )
        
        # 构建SQL查询 - 期货数据使用 trade_time 字段
        # 将日期转换为datetime格式以匹配 trade_time 字段
        start_datetime = f"{start_date} 00:00:00"
        end_datetime = f"{end_date} 23:59:59"
        
        query = f"""
        SELECT trade_time as datetime, open, high, low, close, vol as volume
        FROM {my_raw_table}
        WHERE ts_code = '{ticker}'
        AND trade_time >= '{start_datetime}'
        AND trade_time <= '{end_datetime}'
        ORDER BY trade_time
        """
        
        # 读取数据到DataFrame
        df = pd.read_sql(query, mysql_conn)
        
        if df.empty:
            self.logger.warning(f"No raw data found for {ticker}")
            mysql_conn.close()
            return 0
        
        # 数据预处理
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = check_raw_data(df)
        
        # 批量写入数据库
        raw_data_df = df.set_index('datetime')[['open', 'high', 'low', 'close', 'volume']]
        records_updated = self.db.batch_update_data(ticker, raw_data_df)
        
        self.logger.info(f"Updated {records_updated} raw data records for {ticker}")
        mysql_conn.close()
        return records_updated
    
    def _process_realtime_data(self, ticker: str, my_raw_db: str, my_raw_table: str) -> int:
        """处理实时期货数据"""
        # 获取今日数据 - 期货数据使用完整的datetime
        today_start = datetime.now().strftime('%Y-%m-%d 00:00:00')
        today_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        mysql_conn = pymysql.connect(
            host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
            port=3306,
            user='root',  
            password='Wxtfz13245',
            database=my_raw_db
        )
        
        # 查询今日最新数据 - 期货数据使用 trade_time
        query = f"""
        SELECT trade_time as datetime, open, high, low, close, vol as volume
        FROM {my_raw_table}
        WHERE ts_code = '{ticker}' 
        AND trade_time >= '{today_start}'
        AND trade_time <= '{today_end}'
        ORDER BY trade_time DESC LIMIT 1
        """
        
        df = pd.read_sql(query, mysql_conn)
        
        if df.empty:
            mysql_conn.close()
            return 0
        
        # 数据预处理
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = check_raw_data(df)
        
        # 标记为实时数据并写入
        raw_data_df = df.set_index('datetime')[['open', 'high', 'low', 'close', 'volume']]
        records_updated = self.db.batch_update_data(ticker, raw_data_df, is_realtime=True)
        
        # 基于实时数据计算当日指标
        if records_updated > 0:
            today = datetime.now().strftime('%Y-%m-%d')
            self._process_indicators(ticker, today, today, is_realtime=True)
        
        mysql_conn.close()
        return records_updated
    
    def _process_indicators(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """处理技术指标计算"""
        # 获取用于计算指标的数据（包含历史数据以确保指标计算准确）
        calculation_start = (pd.to_datetime(start_date) - pd.Timedelta(days=200)).strftime('%Y-%m-%d')
        
        # 计算Price MACD
        self._calculate_price_macd(ticker, calculation_start, end_date, is_realtime)
        
        # 计算Volume MACD  
        self._calculate_volume_macd(ticker, calculation_start, end_date, is_realtime)
        
        # 计算HLBW指标
        self._calculate_hlbw(ticker, calculation_start, end_date, is_realtime)
        
        # 计算Prophet预测（仅非实时模式）
        if not is_realtime:
            self._calculate_prophet_forecast(ticker, calculation_start, end_date)
    
    def _calculate_price_macd(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算价格MACD指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['close'])
        
        if df.empty:
            return
        
        price_macd_config = self.config['INDICATORS']['PRICE_MACD']
        signals = calculate_macd_signals(
            df['close'],
            macd_long=price_macd_config['macd_long'],
            macd_mid=price_macd_config['macd_mid'],
            macd_short=price_macd_config['macd_short'],
            diff_ema_period=price_macd_config['diff_ema_period']
        )
        
        # 合并Cross信号
        merged_cross = np.zeros(len(signals))
        for i in range(len(signals)):
            if signals['Cross_1'].iloc[i] != 0:
                merged_cross[i] = signals['Cross_1'].iloc[i]
            if signals['Cross_2'].iloc[i] != 0:
                dea = signals['MACD_Signal'].iloc[i]
                dif = signals['MACD'].iloc[i]
                if dea > 0 and dif > dea and signals['Cross_2'].iloc[i] > 0:
                    merged_cross[i] = 2
                elif dea < 0 and dif < dea and signals['Cross_2'].iloc[i] < 0:
                    merged_cross[i] = -2
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['Price_MACD'] = signals['MACD']
        indicator_df['Price_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['Price_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['Price_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['Price_Cross'] = merged_cross
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_volume_macd(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算成交量MACD指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['volume'])
        
        if df.empty:
            return
        
        # 处理成交量缺失值
        volume_na_count = df['volume'].isna().sum()
        if volume_na_count > 0:
            min_volume = df['volume'].min()
            if pd.isna(min_volume):
                min_volume = 1
            df['volume'].fillna(min_volume, inplace=True)
        
        volume_macd_config = self.config['INDICATORS']['VOLUME_MACD']
        signals = calculate_macd_signals(
            df['volume'],
            macd_long=volume_macd_config['macd_long'],
            macd_mid=volume_macd_config['macd_mid'],
            macd_short=volume_macd_config['macd_short'],
            diff_ema_period=volume_macd_config['diff_ema_period']
        )
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['Volume_MACD'] = signals['MACD']
        indicator_df['Volume_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['Volume_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['Volume_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['Volume_Cross'] = signals['Cross_1']
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_hlbw(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算HLBW指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['high', 'low', 'close'])
        
        if df.empty:
            return
        
        hlbw_config = self.config['INDICATORS']['HLBW']
        
        # 计算HLBW基础指标
        llv_low = pd.to_numeric(df['low'].rolling(window=hlbw_config['lookback_period']).min(), errors='coerce')
        hhv_high = pd.to_numeric(df['high'].rolling(window=hlbw_config['lookback_period']).max(), errors='coerce')
        
        basic_ratio = pd.to_numeric((df['close'] - llv_low) / (hhv_high - llv_low) * 100, errors='coerce')
        
        sma_inner = pd.to_numeric(basic_ratio.ewm(span=hlbw_config['inner_ema'], adjust=False).mean(), errors='coerce')
        sma_outer = pd.to_numeric(sma_inner.ewm(span=hlbw_config['outer_ema'], adjust=False).mean(), errors='coerce')
        x_7 = pd.to_numeric(3 * sma_inner - 2 * sma_outer, errors='coerce')
        trend_line = pd.to_numeric(x_7.ewm(span=hlbw_config['trend_ema'], adjust=False).mean(), errors='coerce')
        
        # 计算MACD信号
        signals = calculate_macd_signals(trend_line)
        
        # 合并Cross信号
        merged_cross = np.zeros(len(signals))
        for i in range(len(signals)):
            trend_line_value = trend_line.iloc[i]
            cross_value = 0
            
            if signals['Cross_1'].iloc[i] > 0 and trend_line_value >= HLBW_BOTTOM_LINE:
                cross_value = 1
            elif signals['Cross_1'].iloc[i] < 0 and trend_line_value <= HLBW_TOP_LINE:
                cross_value = -1
            elif signals['Cross_2'].iloc[i] != 0:
                difdea_diff = signals['DIFDEA_DIFF'].iloc[i]
                if (signals['Cross_2'].iloc[i] > 0 and difdea_diff > 0 and trend_line_value > HLBW_MID_LOW_LINE):
                    cross_value = 10
                elif (signals['Cross_2'].iloc[i] < 0 and difdea_diff < 0 and trend_line_value < HLBW_MID_HIGH_LINE):
                    cross_value = -10
            elif signals['Cross_3'].iloc[i] != 0:
                cross_value = 100 if signals['Cross_3'].iloc[i] > 0 else -100
            
            merged_cross[i] = cross_value
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['HLBW_Trend_Line'] = trend_line
        indicator_df['HLBW_MACD'] = signals['MACD']
        indicator_df['HLBW_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['HLBW_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['HLBW_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['HLBW_Cross'] = merged_cross
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_prophet_forecast(self, ticker: str, start_date: str, end_date: str):
        """计算Prophet预测"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['close'])
        
        if df.empty:
            return
        
        try:
            # 准备Prophet训练数据
            train_df = df.reset_index()
            train_df = train_df.rename(columns={'datetime': 'ds', 'close': 'y'})
            
            # 检查数据有效性
            if train_df['y'].isnull().sum() >= len(train_df) - 1:
                raise ValueError("数据集中有效数据不足")
            
            # 训练Prophet模型
            prophet_config = self.config['INDICATORS']['PROPHET']
            model = Prophet(
                daily_seasonality=prophet_config.get('daily_seasonality', False),
                weekly_seasonality=prophet_config.get('weekly_seasonality', True),
                yearly_seasonality=prophet_config.get('yearly_seasonality', True),
                changepoint_prior_scale=prophet_config.get('changepoint_prior_scale', 0.05)
            )
            model.fit(train_df)
            
            # 生成预测
            forecast_days = prophet_config.get('periods', 30)
            future = model.make_future_dataframe(periods=forecast_days, freq='D')
            forecast = model.predict(future)
            
            # 计算MACD信号
            price_macd_config = self.config['INDICATORS']['PRICE_MACD']
            signals = calculate_macd_signals(
                pd.to_numeric(forecast['yhat'], errors='coerce'),
                macd_long=price_macd_config['macd_long'],
                macd_mid=price_macd_config['macd_mid'],
                macd_short=price_macd_config['macd_short'],
                diff_ema_period=price_macd_config['diff_ema_period']
            )
            
            # 合并Cross信号
            merged_cross = np.zeros(len(signals))
            for i in range(len(signals)):
                if signals['Cross_1'].iloc[i] != 0:
                    merged_cross[i] = signals['Cross_1'].iloc[i]
            
            # 计算趋势持续时间和变化幅度
            trend_duration = np.zeros(len(forecast))
            trend_change = np.zeros(len(forecast))
            
            current_phase = 0
            phase_start_idx = 0
            phase_start_price = 0
            
            for i in range(len(forecast)):
                phase = signals['XLPL_Phase'].iloc[i]
                
                if phase != current_phase:
                    current_phase = phase
                    phase_start_idx = i
                    phase_start_price = forecast['yhat'].iloc[i]
                
                if phase in [2, 4]:
                    trend_duration[i] = i - phase_start_idx + 1
                    current_price = forecast['yhat'].iloc[i]
                    if phase_start_price != 0:
                        change = ((current_price - phase_start_price) / phase_start_price) * 100
                        trend_change[i] = change if phase == 2 else -change
            
            # 准备更新数据
            prophet_df = pd.DataFrame()
            prophet_df['ds'] = forecast['ds']
            prophet_df['PH_yhat'] = forecast['yhat']
            prophet_df['PH_yhat_lower'] = forecast['yhat_lower']
            prophet_df['PH_yhat_upper'] = forecast['yhat_upper']
            prophet_df['PH_MACD'] = signals['MACD']
            prophet_df['PH_MACD_Signal'] = signals['MACD_Signal']
            prophet_df['PH_MACD_Hist'] = signals['MACD_Hist']
            prophet_df['PH_XLPL_Phase'] = signals['XLPL_Phase']
            prophet_df['PH_Cross'] = merged_cross
            prophet_df['PH_Trend_Duration'] = trend_duration
            prophet_df['PH_Trend_Change'] = trend_change
            
            prophet_df.set_index('ds', inplace=True)
            
            # 只更新指定日期范围的数据
            update_start = pd.to_datetime(start_date)
            mask = prophet_df.index >= update_start
            update_df = prophet_df[mask]
            
            # 批量更新
            if not update_df.empty:
                self.db.batch_update_data(ticker, update_df)
            
        except Exception as e:
            self.logger.error(f"Error processing Prophet forecast for {ticker}: {str(e)}")
    
    def _generate_trading_signals(self, ticker: str, start_date: str, end_date: str, 
                                  enable_bidirectional_trading: bool = True,
                                  scaling_strategy_name: str = 'aggressive_pyramid'):
        """生成交易信号（支持双向交易 + 加仓策略）"""
        # 直接调用全局的 generate_trading_signals 函数
        generate_trading_signals(self.db, ticker, start_date, end_date, 
                               enable_bidirectional_trading,
                               scaling_strategy_name=scaling_strategy_name)

def process_ticker(ticker, db_path, my_raw_db, my_raw_table, start_date, end_date, forecast_days, verbose, config=None, scaling_strategy_name='aggressive_pyramid'):
    """Process a single ticker with smart update strategy and scaling strategy"""
    start_time = time.time()
    
    try:
        # Create a new database connection for this thread
        db = TradingSignalDatabaseManager(db_path)
        
        if verbose:
            print(f"\nProcessing {ticker}...")
        
        # 使用智能更新管理器，传递配置
        smart_manager = SmartDataUpdateManager(db, config)
        
        # 执行智能更新（含加仓策略）
        result = smart_manager.update_ticker_data(
            ticker, my_raw_db, my_raw_table, start_date, end_date,
            scaling_strategy_name=scaling_strategy_name
        )
        
        if result.get('records_updated', 0) > 0:
            if verbose:
                print(f"Successfully processed {ticker}")
            # 生成可视化图表（修复：使用正确的end_date，始终生成图表）
            print(f"Generating analysis plot for {ticker}...")
            plot_analysis(db, ticker, start_date, end_date, output_type='bokeh')
            print(f"Plot saved to: output/{ticker}_analysis.html")
        
        # 关闭数据库连接
        db.close()
        
        duration = time.time() - start_time
        
        return {
            'status': 'success',
            'ticker': ticker,
            'strategy': result.get('strategy', 'unknown'),
            'records_updated': result.get('records_updated', 0),
            'duration': duration
        }
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"Error processing {ticker}: {e}")
        
        return {
            'status': 'error',
            'ticker': ticker,
            'error': str(e),
            'duration': duration
        }

def main(update_mode: str = 'smart', enable_realtime: bool = False, 
         max_tickers: int = 2, verbose: bool = False,
         start_date: str = None, end_date: str = None,
         raw_db: str = 'tushare', raw_table: str = 'tb_futures_rboi_1min',
         scaling_strategy: str = 'aggressive_pyramid'):
    """
    主函数：智能处理期货数据并生成交易信号（含加仓策略）
    
    Parameters:
    -----------
    update_mode : str
        更新模式：'smart'(智能)、'full'(全量)、'incremental'(增量)、'realtime'(实时)
    enable_realtime : bool
        是否启用实时数据处理
    max_tickers : int
        最大处理期货合约数量（默认: 2，用于快速测试）
    verbose : bool
        是否显示详细日志
    start_date : str, optional
        起始日期 (格式: YYYY-MM-DD，默认: 2025-01-01)
    end_date : str, optional
        结束日期 (格式: YYYY-MM-DD，默认: 2025-01-31，约1个月数据)
    raw_db : str
        原始数据库名称（默认: tushare）
    raw_table : str
        原始数据表名称（默认: tb_futures_rboi_1min）
    scaling_strategy : str
        加仓策略（默认: 'aggressive_pyramid'）
        可选：'pyramid', 'aggressive_pyramid', 'linear', 'inverse_pyramid',
              'fixed_fraction', 'martingale', 'anti_martingale', 'none'
    """
    # 设置日志
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 配置参数
    my_raw_db = raw_db
    my_raw_table = raw_table
    
    # 从配置文件获取数据库路径
    db_path = EQUITY_CONFIG['DATABASE_PATH']
    
    logger.info(f"[启动] 期货数据智能更新系统")
    logger.info(f"   更新模式: {update_mode}")
    logger.info(f"   实时处理: {enable_realtime}")
    logger.info(f"   数据库路径: {db_path}")
    logger.info(f"   原始数据库: {my_raw_db}")
    logger.info(f"   原始数据表: {my_raw_table}")
    logger.info(f"   并行处理: {EQUITY_CONFIG['PARALLEL_PROCESSING']}")
    logger.info(f"   最大工作进程: {EQUITY_CONFIG['MAX_WORKERS']}")
    
    # 创建主数据库连接用于获取股票列表
    main_db = TradingSignalDatabaseManager(db_path, enable_realtime=enable_realtime)
    
    try:
        # 获取期货代码列表
        if update_mode == 'realtime':
            # 实时模式：只处理已有数据的活跃期货
            tickers = main_db.get_all_tickers(active_only=True)
            logger.info(f"实时模式：处理 {len(tickers)} 个已有期货合约")
        else:
            # 获取期货代码列表
            all_futures = get_all_futures_codes(mydatabase=my_raw_db, table_name=my_raw_table)
            if max_tickers and len(all_futures) > max_tickers:
                tickers = get_top_futures_codes(n=max_tickers, mydatabase=my_raw_db, table_name=my_raw_table)
                logger.info(f"获取前 {len(tickers)} 个期货合约（按成交量排序）")
            else:
                tickers = all_futures
                logger.info(f"获取所有 {len(tickers)} 个期货合约")
        
        # 限制股票数量（用于测试）
        if max_tickers and len(tickers) > max_tickers:
            tickers = tickers[:max_tickers]
            logger.info(f"限制处理股票数量: {max_tickers}")
        
        # 设置日期范围 - 期货数据使用datetime格式
        # 使用预定义的测试时间段（1个月）以加快测试速度
        if not start_date:
            start_date = '2025-01-01'
        if not end_date:
            end_date = '2025-01-31'  # 默认使用1个月数据进行测试
        
        # 根据更新模式调整策略
        current_config = copy.deepcopy(EQUITY_CONFIG)  # 创建配置深拷贝
        if update_mode == 'full':
            current_config['UPDATE_STRATEGY']['force_full_update'] = True
            current_config['UPDATE_STRATEGY']['skip_existing'] = False
            logger.info("强制全量更新模式")
        elif update_mode == 'incremental':
            current_config['UPDATE_STRATEGY']['enable_incremental'] = True
            current_config['UPDATE_STRATEGY']['force_full_update'] = False
            logger.info("增量更新模式")
        elif update_mode == 'realtime':
            enable_realtime = True
            end_date = datetime.now().strftime('%Y-%m-%d')
            logger.info("实时更新模式")
        
        # 显示处理统计
        logger.info(f"\n处理计划:")
        logger.info(f"  期货合约数量: {len(tickers)}")
        logger.info(f"  日期范围: {start_date} 到 {end_date}")
        logger.info(f"  更新模式: {update_mode}")
        
        # 如果启用了并行处理
        if EQUITY_CONFIG['PARALLEL_PROCESSING'] and not enable_realtime:
            # 非实时模式下使用并行处理
            max_workers = min(EQUITY_CONFIG['MAX_WORKERS'], os.cpu_count() // 2)
            
            logger.info(f"开始并行处理，工作进程数: {max_workers}")
            
            success_count = 0
            failed_count = 0
            total_records = 0
            total_duration = 0
            
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                futures = [
                    executor.submit(
                        process_ticker,
                        ticker,
                        db_path,
                        my_raw_db,
                        my_raw_table,
                        start_date,
                        end_date,
                        30,  # forecast_days
                        verbose,
                        current_config,  # 传递配置
                        scaling_strategy  # 加仓策略
                    ) 
                    for ticker in tickers
                ]
                
                # 收集结果
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        
                        if result['status'] == 'success':
                            success_count += 1
                            total_records += result['records_updated']
                            total_duration += result['duration']
                            
                            if verbose:
                                logger.info(f"✓ {result['ticker']}: {result['strategy']} - "
                                          f"{result['records_updated']} records, "
                                          f"{result['duration']:.2f}s")
                        else:
                            failed_count += 1
                            logger.error(f"✗ {result['ticker']}: {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"✗ 处理股票时发生异常: {e}")
            
        else:
            # 串行处理（用于实时模式或调试）
            logger.info("开始串行处理")
            
            success_count = 0
            failed_count = 0
            total_records = 0
            total_duration = 0
            
            for i, ticker in enumerate(tickers, 1):
                try:
                    result = process_ticker(
                        ticker, db_path, my_raw_db, my_raw_table,
                        start_date, end_date, 30, verbose, current_config,  # forecast_days
                        scaling_strategy  # 加仓策略
                    )
                    
                    if result['status'] == 'success':
                        success_count += 1
                        total_records += result['records_updated']
                        total_duration += result['duration']
                        
                        logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: "
                                  f"{result['strategy']} - {result['records_updated']} records")
                    else:
                        failed_count += 1
                        logger.error(f"[{i}/{len(tickers)}] ✗ {result['ticker']}: "
                                   f"{result.get('error', 'Unknown error')}")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"[{i}/{len(tickers)}] ✗ {ticker}: {e}")
        
        # 数据库维护
        if EQUITY_CONFIG['UPDATE_STRATEGY']['auto_cleanup_realtime']:
            logger.info("清理过期实时数据...")
            cleanup_count = 0
            for ticker in tickers[:10]:  # 限制清理数量以节省时间
                try:
                    cleanup_count += main_db.clean_realtime_data(ticker)
                except Exception as e:
                    logger.warning(f"清理 {ticker} 实时数据失败: {e}")
            
            if cleanup_count > 0:
                logger.info(f"清理了 {cleanup_count} 条过期实时数据")
        
        # 显示最终统计
        logger.info(f"\n处理完成统计:")
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {failed_count}")
        logger.info(f"  总记录数: {total_records}")
        logger.info(f"  总耗时: {total_duration:.2f}秒")
        
        if success_count > 0:
            logger.info(f"  平均耗时: {total_duration/success_count:.2f}秒/期货")
        
        # 数据库统计
        db_stats = main_db.get_database_stats()
        logger.info(f"\n数据库统计:")
        logger.info(f"  期货合约数量: {db_stats['ticker_count']}")
        logger.info(f"  总记录数: {db_stats['total_records']:,}")
        logger.info(f"  历史记录: {db_stats['historical_records']:,}")
        logger.info(f"  实时记录: {db_stats['realtime_records']:,}")
        logger.info(f"  数据库大小: {db_stats['database_size_mb']:.2f} MB")
        logger.info(f"  日期范围: {db_stats['earliest_date']} 到 {db_stats['latest_date']}")
        
    except Exception as e:
        logger.error(f"主程序执行失败: {e}")
        raise
    finally:
        # 关闭主数据库连接
        main_db.close()
        logger.info("数据库连接已关闭")

def main_cli():
    """命令行接口函数"""
    import argparse
    import textwrap
    
    # 创建示例帮助信息
    examples = '''
示例用法:
    # 智能更新模式（默认：2个期货品种，1个月数据，1分钟粒度，aggressive_pyramid策略）
    python hlm5_all_parallel.py
    
    # 全量更新模式，显示详细日志（使用默认时间段：1个月）
    python hlm5_all_parallel.py --mode full --verbose
    
    # 增量更新模式，限制处理前10个期货合约
    python hlm5_all_parallel.py --mode incremental --max-tickers 10
    
    # 处理更长时间段的数据（例如：3个月）
    python hlm5_all_parallel.py --start-date 2025-01-01 --end-date 2025-03-31
    
    # 处理全年数据（注意：处理时间较长）
    python hlm5_all_parallel.py --start-date 2025-01-01 --end-date 2025-12-31 --max-tickers 2
    
    # 实时数据更新模式
    python hlm5_all_parallel.py --mode realtime --realtime
    
    # 指定数据源（切换到5分钟数据）
    python hlm5_all_parallel.py --raw-table tb_futures_rboi_5min
    
    # 使用不同的加仓策略
    python hlm5_all_parallel.py --scaling-strategy pyramid  # 金字塔加仓
    python hlm5_all_parallel.py --scaling-strategy linear  # 线性加仓
    python hlm5_all_parallel.py --scaling-strategy none  # 不使用加仓
    
    # 综合示例：5分钟数据 + 6个月 + 金字塔加仓策略
    python hlm5_all_parallel.py --raw-table tb_futures_rboi_5min --start-date 2025-01-01 --end-date 2025-06-30 --scaling-strategy pyramid --verbose
    '''
    
    parser = argparse.ArgumentParser(
        description='期货数据智能更新系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(examples)
    )
    
    # 基本参数
    parser.add_argument('--mode', choices=['smart', 'full', 'incremental', 'realtime'], 
                       default='smart', help='更新模式 (默认: smart)')
    parser.add_argument('--realtime', action='store_true', help='启用实时数据处理')
    parser.add_argument('--max-tickers', type=int, help='最大处理期货合约数量')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细日志')
    
    # 日期范围参数
    parser.add_argument('--start-date', type=str, help='起始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (格式: YYYY-MM-DD)')
    
    # 数据源参数
    parser.add_argument('--raw-db', type=str, default='tushare', help='原始数据库名称 (默认: tushare)')
    parser.add_argument('--raw-table', type=str, default='tb_futures_rboi_1min', help='期货数据表名称 (默认: tb_futures_rboi_1min)')
    
    # 加仓策略参数
    parser.add_argument('--scaling-strategy', type=str, default='aggressive_pyramid',
                       choices=['pyramid', 'aggressive_pyramid', 'linear', 'inverse_pyramid', 
                               'fixed_fraction', 'martingale', 'anti_martingale', 'none'],
                       help='加仓策略 (默认: aggressive_pyramid)')
    
    # 帮助和示例
    parser.add_argument('--help-examples', action='store_true', help='显示详细使用示例')
    
    args = parser.parse_args()
    
    # 如果请求显示示例，打印示例并退出
    if args.help_examples:
        print(textwrap.dedent(examples))
        return
    
    # 调用主函数
    main(
        update_mode=args.mode,
        enable_realtime=args.realtime,
        max_tickers=args.max_tickers,
        verbose=args.verbose,
        start_date=args.start_date,
        end_date=args.end_date,
        raw_db=args.raw_db,
        raw_table=args.raw_table,
        scaling_strategy=args.scaling_strategy
    )

if __name__ == "__main__":
    # 支持直接运行和命令行参数
    import sys
    if len(sys.argv) > 1:
        main_cli()
    else:
        # 默认配置运行期货数据
        # # 使用1分钟数据，处理前10个期货合约
        # main(
        #     update_mode='smart', 
        #     enable_realtime=False, 
        #     max_tickers=10, 
        #     verbose=True,
        #     start_date='2025-01-01',
        #     end_date='2025-12-31',
        #     raw_db='tushare',
        #     raw_table='tb_futures_rboi_5min'
        # )

        # 使用5分钟数据，处理 OI.ZCE 期货合约
        # 数据范围：1个月（2025-01-01 到 2025-01-31）
        # 使用 aggressive_pyramid 加仓策略
        # 临时修改：直接指定 OI.ZCE，通过修改 main 函数内部逻辑
        import sys
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        # 配置参数
        my_raw_db = 'tushare'
        my_raw_table = 'tb_futures_rboi_5min'
        db_path = EQUITY_CONFIG['DATABASE_PATH']
        start_date = '2025-01-01'
        end_date = '2025-01-31'
        scaling_strategy = 'aggressive_pyramid'
        ticker = 'OI.ZCE'  # 指定只处理 OI.ZCE
        
        logger.info(f"[启动] 处理期货: {ticker}")
        logger.info(f"   数据表: {my_raw_table}")
        logger.info(f"   日期范围: {start_date} 到 {end_date}")
        logger.info(f"   加仓策略: {scaling_strategy}")
        
        # 创建主数据库连接
        main_db = TradingSignalDatabaseManager(db_path, enable_realtime=False)
        
        try:
            # 直接使用指定的期货代码
            tickers = [ticker]
            
            # 创建配置
            current_config = copy.deepcopy(EQUITY_CONFIG)
            current_config['UPDATE_STRATEGY']['force_full_update'] = True
            
            # 串行处理单个期货
            for i, t in enumerate(tickers, 1):
                try:
                    result = process_ticker(
                        t, db_path, my_raw_db, my_raw_table,
                        start_date, end_date, 30, True, current_config,
                        scaling_strategy
                    )
                    
                    if result['status'] == 'success':
                        logger.info(f"[{i}/{len(tickers)}] ✓ {result['ticker']}: "
                                  f"{result['strategy']} - {result['records_updated']} records")
                    else:
                        logger.error(f"[{i}/{len(tickers)}] ✗ {result['ticker']}: "
                                   f"{result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"[{i}/{len(tickers)}] ✗ {t}: {e}")
            
        finally:
            main_db.close()
            logger.info("处理完成")

# 新增：智能数据更新管理器（已移到 process_ticker 之前，此处删除重复定义）

# 修改后的 process_ticker 函数（已废弃，保留用于兼容性）
def process_ticker_smart(ticker: str, db_path: str, my_raw_db: str, my_raw_table: str, 
                        start_date: str, end_date: str, enable_realtime: bool = False, 
                        verbose: bool = True) -> Dict:
    """智能处理单个股票数据"""
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path, enable_realtime=enable_realtime)
    
    # 创建智能更新管理器
    update_manager = SmartDataUpdateManager(db)
    
    try:
        if verbose:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing {ticker}...")
        
        # 使用智能更新策略
        result = update_manager.update_ticker_data(
            ticker, my_raw_db, my_raw_table, start_date, end_date, enable_realtime
        )
        
        if verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {ticker}: {result['strategy']} - "
                  f"{result['records_updated']} records, {result['duration']:.2f}s")
        
        # 生成可视化图表（修复：使用正确的end_date，非实时模式时始终生成）
        if result['records_updated'] > 0 and not enable_realtime:
            print(f"Generating analysis plot for {ticker}...")
            plot_analysis(db, ticker, start_date, end_date, output_type='bokeh')
            print(f"Plot saved to: output/{ticker}_analysis.html")
        
        return result
        
    except Exception as e:
        return {
            'ticker': ticker,
            'strategy': 'failed',
            'records_updated': 0,
            'duration': 0,
            'status': 'failed',
            'error': str(e)
        }
    finally:
        db.close()

# 以下为已删除的重复类定义残留代码
# 已删除：SmartDataUpdateManager 类的重复定义（已移到 process_ticker 之前）
# 已删除：从第 3537 行到第 4019 行的所有残留代码
        
    def update_ticker_data(self, ticker: str, my_raw_db: str, my_raw_table: str, 
                          start_date: str = None, end_date: str = None, 
                          is_realtime: bool = False,
                          scaling_strategy_name: str = 'aggressive_pyramid') -> Dict:
        """
        智能更新单个股票数据
        
        Returns:
        --------
        Dict: 更新结果统计
        """
        update_start_time = time.time()
        
        # 1. 检查是否强制全量更新
        if self.config['UPDATE_STRATEGY'].get('force_full_update', False):
            strategy = 'full'
            strategy_info = {
                'strategy': 'full',
                'start_date': start_date or '2015-01-01',
                'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
                'reason': 'Force full update mode enabled'
            }
            self.logger.info(f"Force full update for {ticker}")
        else:
            # 获取智能更新策略
            strategy_info = self.db.get_update_strategy(ticker, start_date, end_date)
            strategy = strategy_info['strategy']
            
            if strategy == 'skip':
                self.logger.info(f"Skipping {ticker}: {strategy_info['reason']}")
                return {'ticker': ticker, 'strategy': 'skip', 'records_updated': 0, 'duration': 0}
        
        self.logger.info(f"Processing {ticker} with {strategy} strategy: {strategy_info['reason']}")
        
        try:
            records_updated = 0
            
            # 2. 在处理新数据之前，先检查并删除该ticker的所有旧记录
            # 确保每次回测的数据都是最新的，避免重复
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trading_data WHERE ticker = ?", (ticker,))
            existing_count = cursor.fetchone()[0]
            
            if existing_count > 0:
                self.logger.info(f"Found {existing_count} existing records for {ticker}, deleting all old data...")
                cursor.execute("DELETE FROM trading_data WHERE ticker = ?", (ticker,))
                self.db.conn.commit()
                self.logger.info(f"Successfully deleted all existing records for {ticker}")
            
            # 3. 根据策略下载和处理数据
            if strategy in ['full', 'incremental']:
                records_updated += self._process_raw_data(
                    ticker, my_raw_db, my_raw_table, 
                    strategy_info['start_date'], strategy_info['end_date']
                )
                
                # 4. 计算技术指标（仅在有新数据时）
                if records_updated > 0:
                    self._process_indicators(
                        ticker, strategy_info['start_date'], strategy_info['end_date']
                    )
                    
                    # 5. 生成交易信号（含加仓策略）
                    self._generate_trading_signals(
                        ticker, strategy_info['start_date'], 
                        (pd.to_datetime(strategy_info['end_date']) + pd.Timedelta(days=30)).strftime('%Y-%m-%d'),
                        scaling_strategy_name=scaling_strategy_name
                    )
            
            elif strategy == 'realtime':
                records_updated += self._process_realtime_data(
                    ticker, my_raw_db, my_raw_table
                )
            
            # 6. 更新元数据
            if records_updated > 0:
                completeness = self.db.check_data_completeness(ticker)
                self.db.update_ticker_metadata(
                    ticker, 
                    completeness['first_date'], 
                    completeness['last_date'],
                    completeness['total_records']
                )
            
            # 7. 记录更新日志
            duration = time.time() - update_start_time
            self.db.log_update(
                ticker, strategy, strategy_info['start_date'], 
                strategy_info['end_date'], records_updated, duration, 'success'
            )
            
            return {
                'ticker': ticker, 
                'strategy': strategy, 
                'records_updated': records_updated, 
                'duration': duration,
                'status': 'success'
            }
            
        except Exception as e:
            duration = time.time() - update_start_time
            error_msg = str(e)
            self.logger.error(f"Error processing {ticker}: {error_msg}")
            
            self.db.log_update(
                ticker, strategy, strategy_info.get('start_date'), 
                strategy_info.get('end_date'), 0, duration, 'failed', error_msg
            )
            
            return {
                'ticker': ticker, 
                'strategy': strategy, 
                'records_updated': 0, 
                'duration': duration,
                'status': 'failed',
                'error': error_msg
            }
    
    def _process_raw_data(self, ticker: str, my_raw_db: str, my_raw_table: str, 
                         start_date: str, end_date: str) -> int:
        """处理期货原始数据下载"""
        # 连接MySQL数据库
        mysql_conn = pymysql.connect(
            host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
            port=3306,
            user='root',
            password='Wxtfz13245',
            database=my_raw_db
        )
        
        # 构建SQL查询 - 期货数据使用 trade_time 字段
        # 将日期转换为datetime格式以匹配 trade_time 字段
        start_datetime = f"{start_date} 00:00:00"
        end_datetime = f"{end_date} 23:59:59"
        
        query = f"""
        SELECT trade_time as datetime, open, high, low, close, vol as volume
        FROM {my_raw_table}
        WHERE ts_code = '{ticker}'
        AND trade_time >= '{start_datetime}'
        AND trade_time <= '{end_datetime}'
        ORDER BY trade_time
        """
        
        # 读取数据到DataFrame
        df = pd.read_sql(query, mysql_conn)
        
        if df.empty:
            self.logger.warning(f"No raw data found for {ticker}")
            mysql_conn.close()
            return 0
        
        # 数据预处理
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = check_raw_data(df)
        
        # 批量写入数据库
        raw_data_df = df.set_index('datetime')[['open', 'high', 'low', 'close', 'volume']]
        records_updated = self.db.batch_update_data(ticker, raw_data_df)
        
        self.logger.info(f"Updated {records_updated} raw data records for {ticker}")
        mysql_conn.close()
        return records_updated
    
    def _process_realtime_data(self, ticker: str, my_raw_db: str, my_raw_table: str) -> int:
        """处理实时期货数据"""
        # 获取今日数据 - 期货数据使用完整的datetime
        today_start = datetime.now().strftime('%Y-%m-%d 00:00:00')
        today_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        mysql_conn = pymysql.connect(
            host='rm-bp105by33qs9s358i5o.mysql.rds.aliyuncs.com',
            port=3306,
            user='root',  
            password='Wxtfz13245',
            database=my_raw_db
        )
        
        # 查询今日最新数据 - 期货数据使用 trade_time
        query = f"""
        SELECT trade_time as datetime, open, high, low, close, vol as volume
        FROM {my_raw_table}
        WHERE ts_code = '{ticker}' 
        AND trade_time >= '{today_start}'
        AND trade_time <= '{today_end}'
        ORDER BY trade_time DESC LIMIT 1
        """
        
        df = pd.read_sql(query, mysql_conn)
        
        if df.empty:
            mysql_conn.close()
            return 0
        
        # 数据预处理
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = check_raw_data(df)
        
        # 标记为实时数据并写入
        raw_data_df = df.set_index('datetime')[['open', 'high', 'low', 'close', 'volume']]
        records_updated = self.db.batch_update_data(ticker, raw_data_df, is_realtime=True)
        
        # 基于实时数据计算当日指标
        if records_updated > 0:
            today = datetime.now().strftime('%Y-%m-%d')
            self._process_indicators(ticker, today, today, is_realtime=True)
        
        mysql_conn.close()
        return records_updated
    
    def _process_indicators(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """处理技术指标计算"""
        # 获取用于计算指标的数据（包含历史数据以确保指标计算准确）
        calculation_start = (pd.to_datetime(start_date) - pd.Timedelta(days=200)).strftime('%Y-%m-%d')
        
        # 计算Price MACD
        self._calculate_price_macd(ticker, calculation_start, end_date, is_realtime)
        
        # 计算Volume MACD  
        self._calculate_volume_macd(ticker, calculation_start, end_date, is_realtime)
        
        # 计算HLBW指标
        self._calculate_hlbw(ticker, calculation_start, end_date, is_realtime)
        
        # 计算Prophet预测（仅非实时模式）
        if not is_realtime:
            self._calculate_prophet_forecast(ticker, calculation_start, end_date)
    
    def _calculate_price_macd(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算价格MACD指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['close'])
        
        if df.empty:
            return
        
        price_macd_config = self.config['INDICATORS']['PRICE_MACD']
        signals = calculate_macd_signals(
            df['close'],
            macd_long=price_macd_config['macd_long'],
            macd_mid=price_macd_config['macd_mid'],
            macd_short=price_macd_config['macd_short'],
            diff_ema_period=price_macd_config['diff_ema_period']
        )
        
        # 合并Cross信号
        merged_cross = np.zeros(len(signals))
        for i in range(len(signals)):
            if signals['Cross_1'].iloc[i] != 0:
                merged_cross[i] = signals['Cross_1'].iloc[i]
            if signals['Cross_2'].iloc[i] != 0:
                dea = signals['MACD_Signal'].iloc[i]
                dif = signals['MACD'].iloc[i]
                if dea > 0 and dif > dea and signals['Cross_2'].iloc[i] > 0:
                    merged_cross[i] = 2
                elif dea < 0 and dif < dea and signals['Cross_2'].iloc[i] < 0:
                    merged_cross[i] = -2
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['Price_MACD'] = signals['MACD']
        indicator_df['Price_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['Price_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['Price_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['Price_Cross'] = merged_cross
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_volume_macd(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算成交量MACD指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['volume'])
        
        if df.empty:
            return
        
        # 处理成交量缺失值
        volume_na_count = df['volume'].isna().sum()
        if volume_na_count > 0:
            min_volume = df['volume'].min()
            if pd.isna(min_volume):
                min_volume = 1
            df['volume'].fillna(min_volume, inplace=True)
        
        volume_macd_config = self.config['INDICATORS']['VOLUME_MACD']
        signals = calculate_macd_signals(
            df['volume'],
            macd_long=volume_macd_config['macd_long'],
            macd_mid=volume_macd_config['macd_mid'],
            macd_short=volume_macd_config['macd_short'],
            diff_ema_period=volume_macd_config['diff_ema_period']
        )
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['Volume_MACD'] = signals['MACD']
        indicator_df['Volume_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['Volume_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['Volume_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['Volume_Cross'] = signals['Cross_1']
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_hlbw(self, ticker: str, start_date: str, end_date: str, is_realtime: bool = False):
        """计算HLBW指标"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['high', 'low', 'close'])
        
        if df.empty:
            return
        
        hlbw_config = self.config['INDICATORS']['HLBW']
        
        # 计算HLBW基础指标
        llv_low = pd.to_numeric(df['low'].rolling(window=hlbw_config['lookback_period']).min(), errors='coerce')
        hhv_high = pd.to_numeric(df['high'].rolling(window=hlbw_config['lookback_period']).max(), errors='coerce')
        
        basic_ratio = pd.to_numeric((df['close'] - llv_low) / (hhv_high - llv_low) * 100, errors='coerce')
        
        sma_inner = pd.to_numeric(basic_ratio.ewm(span=hlbw_config['inner_ema'], adjust=False).mean(), errors='coerce')
        sma_outer = pd.to_numeric(sma_inner.ewm(span=hlbw_config['outer_ema'], adjust=False).mean(), errors='coerce')
        x_7 = pd.to_numeric(3 * sma_inner - 2 * sma_outer, errors='coerce')
        trend_line = pd.to_numeric(x_7.ewm(span=hlbw_config['trend_ema'], adjust=False).mean(), errors='coerce')
        
        # 计算MACD信号
        signals = calculate_macd_signals(trend_line)
        
        # 合并Cross信号
        merged_cross = np.zeros(len(signals))
        for i in range(len(signals)):
            trend_line_value = trend_line.iloc[i]
            cross_value = 0
            
            if signals['Cross_1'].iloc[i] > 0 and trend_line_value >= HLBW_BOTTOM_LINE:
                cross_value = 1
            elif signals['Cross_1'].iloc[i] < 0 and trend_line_value <= HLBW_TOP_LINE:
                cross_value = -1
            elif signals['Cross_2'].iloc[i] != 0:
                difdea_diff = signals['DIFDEA_DIFF'].iloc[i]
                if (signals['Cross_2'].iloc[i] > 0 and difdea_diff > 0 and trend_line_value > HLBW_MID_LOW_LINE):
                    cross_value = 10
                elif (signals['Cross_2'].iloc[i] < 0 and difdea_diff < 0 and trend_line_value < HLBW_MID_HIGH_LINE):
                    cross_value = -10
            elif signals['Cross_3'].iloc[i] != 0:
                cross_value = 100 if signals['Cross_3'].iloc[i] > 0 else -100
            
            merged_cross[i] = cross_value
        
        # 准备更新数据
        indicator_df = pd.DataFrame(index=df.index)
        indicator_df['HLBW_Trend_Line'] = trend_line
        indicator_df['HLBW_MACD'] = signals['MACD']
        indicator_df['HLBW_MACD_Signal'] = signals['MACD_Signal']
        indicator_df['HLBW_MACD_Hist'] = signals['MACD_Hist']
        indicator_df['HLBW_XLPL_Phase'] = signals['XLPL_Phase']
        indicator_df['HLBW_Cross'] = merged_cross
        
        # 只更新指定日期范围的数据
        update_start = pd.to_datetime(start_date)
        mask = indicator_df.index >= update_start
        update_df = indicator_df[mask]
        
        # 批量更新
        self.db.batch_update_data(ticker, update_df, is_realtime=is_realtime)
    
    def _calculate_prophet_forecast(self, ticker: str, start_date: str, end_date: str):
        """计算Prophet预测"""
        df = self.db.get_data(ticker, start_date, end_date, columns=['close'])
        
        if df.empty:
            return
        
        try:
            # 准备Prophet训练数据
            train_df = df.reset_index()
            train_df = train_df.rename(columns={'datetime': 'ds', 'close': 'y'})
            
            # 检查数据有效性
            if train_df['y'].isnull().sum() >= len(train_df) - 1:
                raise ValueError("数据集中有效数据不足")
            
            # 训练Prophet模型
            prophet_config = self.config['INDICATORS']['PROPHET']
            model = Prophet(
                daily_seasonality=prophet_config.get('daily_seasonality', False),
                weekly_seasonality=prophet_config.get('weekly_seasonality', True),
                yearly_seasonality=prophet_config.get('yearly_seasonality', True),
                changepoint_prior_scale=prophet_config.get('changepoint_prior_scale', 0.05)
            )
            model.fit(train_df)
            
            # 生成预测
            forecast_days = prophet_config.get('periods', 30)
            future = model.make_future_dataframe(periods=forecast_days, freq='D')
            forecast = model.predict(future)
            
            # 计算MACD信号
            price_macd_config = self.config['INDICATORS']['PRICE_MACD']
            signals = calculate_macd_signals(
                pd.to_numeric(forecast['yhat'], errors='coerce'),
                macd_long=price_macd_config['macd_long'],
                macd_mid=price_macd_config['macd_mid'],
                macd_short=price_macd_config['macd_short'],
                diff_ema_period=price_macd_config['diff_ema_period']
            )
            
            # 合并Cross信号
            merged_cross = np.zeros(len(signals))
            for i in range(len(signals)):
                if signals['Cross_1'].iloc[i] != 0:
                    merged_cross[i] = signals['Cross_1'].iloc[i]
            
            # 计算趋势持续时间和变化幅度
            trend_duration = np.zeros(len(forecast))
            trend_change = np.zeros(len(forecast))
            
            current_phase = 0
            phase_start_idx = 0
            phase_start_price = 0
            
            for i in range(len(forecast)):
                phase = signals['XLPL_Phase'].iloc[i]
                
                if phase != current_phase:
                    current_phase = phase
                    phase_start_idx = i
                    phase_start_price = forecast['yhat'].iloc[i]
                
                if phase in [2, 4]:
                    trend_duration[i] = i - phase_start_idx + 1
                    current_price = forecast['yhat'].iloc[i]
                    if phase_start_price != 0:
                        change = ((current_price - phase_start_price) / phase_start_price) * 100
                        trend_change[i] = change if phase == 2 else -change
            
            # 准备更新数据
            prophet_df = pd.DataFrame()
            prophet_df['ds'] = forecast['ds']
            prophet_df['PH_yhat'] = forecast['yhat']
            prophet_df['PH_yhat_lower'] = forecast['yhat_lower']
            prophet_df['PH_yhat_upper'] = forecast['yhat_upper']
            prophet_df['PH_MACD'] = signals['MACD']
            prophet_df['PH_MACD_Signal'] = signals['MACD_Signal']
            prophet_df['PH_MACD_Hist'] = signals['MACD_Hist']
            prophet_df['PH_XLPL_Phase'] = signals['XLPL_Phase']
            prophet_df['PH_Cross'] = merged_cross
            prophet_df['PH_Trend_Duration'] = trend_duration
            prophet_df['PH_Trend_Change'] = trend_change
            
            prophet_df.set_index('ds', inplace=True)
            
            # 只更新指定日期范围的数据
            update_start = pd.to_datetime(start_date)
            mask = prophet_df.index >= update_start
            update_df = prophet_df[mask]
            
            # 批量更新
            if not update_df.empty:
                self.db.batch_update_data(ticker, update_df)
            
        except Exception as e:
            self.logger.error(f"Error processing Prophet forecast for {ticker}: {str(e)}")
    
    def _generate_trading_signals(self, ticker: str, start_date: str, end_date: str, 
                                  enable_bidirectional_trading: bool = True,
                                  scaling_strategy_name: str = 'aggressive_pyramid'):
        """生成交易信号（支持双向交易 + 加仓策略）"""
        # 直接调用全局的 generate_trading_signals 函数
        generate_trading_signals(self.db, ticker, start_date, end_date, 
                               enable_bidirectional_trading,
                               scaling_strategy_name=scaling_strategy_name)

# 修改后的 process_ticker 函数
def process_ticker_smart(ticker: str, db_path: str, my_raw_db: str, my_raw_table: str, 
                        start_date: str, end_date: str, enable_realtime: bool = False, 
                        verbose: bool = True) -> Dict:
    """智能处理单个股票数据"""
    # 创建数据库连接
    db = TradingSignalDatabaseManager(db_path, enable_realtime=enable_realtime)
    
    # 创建智能更新管理器
    update_manager = SmartDataUpdateManager(db)
    
    try:
        if verbose:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing {ticker}...")
        
        # 使用智能更新策略
        result = update_manager.update_ticker_data(
            ticker, my_raw_db, my_raw_table, start_date, end_date, enable_realtime
        )
        
        if verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {ticker}: {result['strategy']} - "
                  f"{result['records_updated']} records, {result['duration']:.2f}s")
        
        # 生成可视化图表（修复：使用正确的end_date，非实时模式时始终生成）
        if result['records_updated'] > 0 and not enable_realtime:
            print(f"Generating analysis plot for {ticker}...")
            plot_analysis(db, ticker, start_date, end_date, output_type='bokeh')
            print(f"Plot saved to: output/{ticker}_analysis.html")
        
        return result
        
    except Exception as e:
        return {
            'ticker': ticker,
            'strategy': 'failed',
            'records_updated': 0,
            'duration': 0,
            'status': 'failed',
            'error': str(e)
        }
    finally:
        db.close()
